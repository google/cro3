// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements dut_service.proto (see proto for details)
package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/url"
	"path"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	"golang.org/x/crypto/ssh"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"chromiumos/lro"
	"chromiumos/test/dut/cmd/cros-dut/dutssh"
	"chromiumos/test/dut/internal"
)

const cacheDownloadURI = "/download/%s"
const cacheUntarAndDownloadURI = "/extract/%s?file=%s"
const cacheExtraAndDownloadURI = "/decompress/%s"

// DutServiceServer implementation of dut_service.proto
type DutServiceServer struct {
	manager        *lro.Manager
	logger         *log.Logger
	connection     dutssh.ClientInterface
	serializerPath string
	protoChunkSize int64
	dutName        string
	wiringAddress  string
	cacheAddress   string
}

// newDutServiceServer creates a new dut service server to listen to rpc requests.
func newDutServiceServer(l net.Listener, logger *log.Logger, conn dutssh.ClientInterface, serializerPath string, protoChunkSize int64, dutName, wiringAddress string, cacheAddress string) (*grpc.Server, func()) {
	s := &DutServiceServer{
		manager:        lro.New(),
		logger:         logger,
		connection:     conn,
		serializerPath: serializerPath,
		protoChunkSize: protoChunkSize,
		dutName:        dutName,
		wiringAddress:  wiringAddress,
		cacheAddress:   cacheAddress,
	}

	server := grpc.NewServer()
	destructor := func() {
		s.connection.Close()
		s.manager.Close()
	}
	api.RegisterDutServiceServer(server, s)
	longrunning.RegisterOperationsServer(server, s.manager)
	logger.Println("dutservice listen to request at ", l.Addr().String())
	return server, destructor
}

// Close closes DUT service.
func (s *DutServiceServer) Close() {
	s.manager.Close()
	s.connection.Close()
}

// FetchFile pulls a file or directory from the remote host.
func (s *DutServiceServer) FetchFile(req *api.FetchFileRequest, stream api.DutService_FetchFileServer) error {
	return status.Error(codes.Unimplemented, "FetchFile unimplemented")
}

// ExecCommand remotely executes a command on the DUT.
func (s *DutServiceServer) ExecCommand(req *api.ExecCommandRequest, stream api.DutService_ExecCommandServer) error {
	s.logger.Println("Received api.ExecCommandRequest: ", req)

	command := req.Command + " " + strings.Join(req.Args, " ")

	var stdin io.Reader
	if len(req.Stdin) > 0 {
		stdin = bytes.NewReader(req.Stdin)

	}

	combined := false
	if req.Stderr == api.Output_OUTPUT_STDOUT {
		combined = true
	}

	resp := s.runCmd(command, stdin, combined)
	return stream.Send(resp)
}

// FetchCrashes remotely fetches crashes from the DUT.
func (s *DutServiceServer) FetchCrashes(req *api.FetchCrashesRequest, stream api.DutService_FetchCrashesServer) error {
	s.logger.Println("Received api.FetchCrashesRequest: ", req)
	if exists, stderr, err := s.runCmdOutput(dutssh.PathExistsCommand(s.serializerPath)); err != nil {
		return status.Errorf(codes.FailedPrecondition, "Failed to check crash_serializer existence: %s", stderr)
	} else if exists != "1" {
		return status.Errorf(codes.NotFound, "crash_serializer not present on device.")
	}

	session, err := s.connection.NewSession()
	if err != nil {
		return status.Errorf(codes.FailedPrecondition, "Failed to start ssh session: %s", err)
	}
	defer session.Close()

	stdout, stderr, err := getPipes(session)
	if err != nil {
		return err
	}

	var wg sync.WaitGroup
	defer wg.Wait()

	wg.Add(1)
	// Grab stderr concurrently to reading the protos.
	go func() {
		defer wg.Done()

		for stderr.Scan() {
			log.Printf("crash_serializer: %s\n", stderr.Text())
		}
		if err := stderr.Err(); err != nil {
			log.Printf("Failed to get stderr: %s\n", err)
		}
	}()

	err = session.Start(dutssh.RunSerializerCommand(s.serializerPath, s.protoChunkSize, req.FetchCore))
	if err != nil {
		return status.Errorf(codes.FailedPrecondition, "Failed to run serializer: %s", err.Error())
	}

	var protoBytes bytes.Buffer

	for {
		crashResp, err := readFetchCrashesProto(stdout, protoBytes)
		if err != nil {
			return err
		} else if crashResp == nil {
			return nil
		}
		_ = stream.Send(crashResp)
	}
}

// Restart is a special case of ExecCommand which restarts the DUT and reconnects
func (s *DutServiceServer) Restart(ctx context.Context, req *api.RestartRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.RestartRequest: ", req)
	op := s.manager.NewOperation()

	// Get the boot ID before rebooting to ensure it changes.
	preBootID, err := s.getBootID(ctx)
	if err != nil {
		s.manager.SetError(op.Name, status.New(codes.Aborted, fmt.Sprintf("failed to get bootID before reboot: %s", err)))
		return op, err
	}

	command := "reboot " + strings.Join(req.Args, " ")

	s.logger.Printf("Rebooting Client.")
	output, bootStderr, _ := s.runCmdOutput(command)
	if bootStderr != "" {
		s.logger.Printf("reboot command stderr: %s", bootStderr)
	}
	s.manager.SetResult(op.Name, &api.RestartResponse{
		Output: output,
	})

	err = s.waitForReboot(ctx, req)
	if err != nil {
		s.manager.SetError(op.Name, status.New(codes.Aborted, fmt.Sprintf("rebootDut: unable to get connection, %s", err)))
		return op, err
	}

	postBootID, err := s.getBootID(ctx)
	if err != nil {
		s.manager.SetError(op.Name, status.New(codes.Aborted, fmt.Sprintf("failed to get bootID after reconnection: %s", err)))
		return op, err
	}

	if preBootID == postBootID || postBootID == "" {
		s.logger.Printf("boot ID pre reboot: %s matches post reboot: %s", preBootID, postBootID)
		s.manager.SetError(op.Name, status.New(codes.Aborted, fmt.Sprint("boot ID did not change after reboot")))
		return op, fmt.Errorf("boot ID did not change after reboot")
	}
	return op, err

}

func (s *DutServiceServer) getBootID(ctx context.Context) (string, error) {
	stdout, stderr, err := s.runCmdOutput("cat /proc/sys/kernel/random/boot_id")
	if err != nil {
		s.logger.Printf("Failed to get bootID:  %s\n, %s", err, stderr)
		return stdout, fmt.Errorf("Failed to get bootID %s", err)
	}

	s.logger.Printf("Found BootID %s", stdout)
	return stdout, nil
}

func (s *DutServiceServer) waitForReboot(ctx context.Context, req *api.RestartRequest) error {
	// Wait so following commands don't run before an actual reboot has kicked off
	// by waiting for the client connection to shutdown or a timeout.
	s.logger.Printf("Waiting for reboot to complete.")

	wait := make(chan interface{})
	go func() {
		s.logger.Printf("Waiting for reboot: Connection wait.")
		_ = s.connection.Wait()
		s.logger.Printf("Waiting for reboot: Connection wait complete.")
		close(wait)
		s.logger.Printf("Waiting for reboot: close wait")

	}()
	select {
	case <-wait:
		s.logger.Printf("Waiting for reboot: GetConnectionWithRetry")
		conn, err := GetConnectionWithRetry(ctx, s.dutName, s.wiringAddress, req, s.logger)
		if err != nil {
			s.logger.Println("unable to connect to dut post reboot.")
			return fmt.Errorf("rebootDut: unable to get connection, %s", err)
		}
		s.logger.Printf("Waiting for reboot: GetConnectionWithRetry completed.")
		s.connection = &dutssh.SSHClient{Client: conn}
		return nil

	case <-ctx.Done():
		s.logger.Println("Failed to reboot within timeout")
		return fmt.Errorf("rebootDUT: timeout waiting for reboot")
	}
}

// RunCmd implements the dutssh.CmdExecutor interface.
func (s *DutServiceServer) RunCmd(cmd string) (*dutssh.CmdResult, error) {
	resp := s.runCmd(cmd, nil, false)
	return &dutssh.CmdResult{
		ReturnCode: resp.ExitInfo.Status,
		StdOut:     string(resp.GetStdout()),
		StdErr:     string(resp.GetStderr()),
	}, nil
}

// DetectDeviceConfigId scans a live device and returns identity info.
func (s *DutServiceServer) DetectDeviceConfigId(
	req *api.DetectDeviceConfigIdRequest,
	stream api.DutService_DetectDeviceConfigIdServer) error {
	resp := internal.DetectDeviceConfigID(s)
	return stream.Send(resp)
}

// Cache downloads a specified file to the DUT via CacheForDut service
func (s *DutServiceServer) Cache(ctx context.Context, req *api.CacheRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.CacheRequest: ", req)
	op := s.manager.NewOperation()

	command := "curl --keepalive-time 20 -S -s -v -# -C - --retry 3 --retry-delay 60"

	destination, err := s.parseDestination(req)

	if err != nil {
		return nil, err
	}
	mkdirPath, err := s.parseDutDest(req)
	if err != nil {
		return nil, err
	}

	if mkdirPath != "" {
		mkdircmd := fmt.Sprintf("mkdir -p %s", mkdirPath)
		s.logger.Printf("Running cmd %s\n", mkdircmd)
		if stdout, stderr, err := s.runCmdOutput(mkdircmd); err != nil {
			s.logger.Printf("Getting error running command '%q' from server to host: %v", mkdircmd, err)
			s.logger.Printf("cmd stdout: %s, cmd stderr: %s", stdout, stderr)
		}
	}
	fullCmd := fmt.Sprintf("%s %s", command, destination)

	if stdout, stderr, err := s.runCmdOutputWithRetry(fullCmd, req.GetRetry()); err != nil {
		s.logger.Printf("Getting error from cache server while running command %q: %v", fullCmd, err)
		s.logger.Printf("stdout: %s, stderr: %s", stdout, stderr)
		status := status.New(codes.Aborted, fmt.Sprintf("err: %s, stderr: %s", err, stderr))
		s.manager.SetError(op.Name, status)
		return op, err
	}

	s.logger.Printf("Command %q was successful", fullCmd)
	s.manager.SetResult(op.Name, &api.CacheResponse{
		Result: &api.CacheResponse_Success_{},
	})

	return op, nil
}

func (s *DutServiceServer) runCmdOutputWithRetry(cmd string, retry *api.CacheRequest_Retry) (stdout string, stderr string, err error) {
	retryCount := 0
	retryInterval := time.Duration(0)

	if retry != nil {
		retryCount = int(retry.Times)
		retryInterval = time.Duration(retry.IntervalMs) * time.Millisecond
	}

	for ; retryCount >= 0; retryCount-- {
		stdout, stderr, err = s.runCmdOutput(cmd)
		if err == nil {
			return
		}
		time.Sleep(retryInterval)
	}
	return
}

func (s *DutServiceServer) parseDutDest(req *api.CacheRequest) (string, error) {
	switch op := req.Destination.(type) {
	case *api.CacheRequest_File:
		// TODO(jaquesc): parse the file name to ensure it's a file and prevent user errors
		return filepath.Dir(op.File.Path), nil
	case *api.CacheRequest_Pipe_:
		s.logger.Println("CACHETYPE PIPE")
		// TODO(dbeckett): verify we really don't want to mkdir of a pipe
		return "", nil
	default:
		return "", fmt.Errorf("destination can only be one of LocalFile or Pipe")
	}
}

func (s *DutServiceServer) parseDestination(req *api.CacheRequest) (string, error) {
	url, err := s.getCacheURL(req)
	if err != nil {
		return "", err
	}

	switch op := req.Destination.(type) {
	case *api.CacheRequest_File:
		// TODO(jaquesc): parse the file name to ensure it's a file and prevent user errors
		return fmt.Sprintf("-o %s %s", op.File.Path, url), nil
	case *api.CacheRequest_Pipe_:
		return fmt.Sprintf("%s | %s", url, op.Pipe.Commands), nil
	default:
		return "", fmt.Errorf("destination can only be one of LocalFile or Pipe")
	}
}

// getCacheURL returns a constructed URL to the caching service given a specific
// Source request type
func (s *DutServiceServer) getCacheURL(req *api.CacheRequest) (string, error) {
	switch op := req.Source.(type) {
	case *api.CacheRequest_GsFile:
		parsedPath, err := parseGSURL(op.GsFile.SourcePath)
		if err != nil {
			return "", err
		}
		return path.Join(s.cacheAddress, fmt.Sprintf(cacheDownloadURI, parsedPath)), nil
	case *api.CacheRequest_GsTarFile:
		parsedPath, err := parseGSURL(op.GsTarFile.SourcePath)
		if err != nil {
			return "", err
		}
		return path.Join(s.cacheAddress, fmt.Sprintf(cacheUntarAndDownloadURI, parsedPath, op.GsTarFile.SourceFile)), nil
	case *api.CacheRequest_GsZipFile:
		parsedPath, err := parseGSURL(op.GsZipFile.SourcePath)
		if err != nil {
			return "", err
		}
		return path.Join(s.cacheAddress, fmt.Sprintf(cacheExtraAndDownloadURI, parsedPath)), nil
	default:
		return "", fmt.Errorf("type can only be one of GsFile, GsTarFile or GSZipFile")
	}
}

// parseGSURL retrieves the bucket and object from a GS URL.
// URL expectation is of the form: "gs://bucket/object"
func parseGSURL(gsURL string) (string, error) {
	if !strings.HasPrefix(gsURL, "gs://") {
		return "", fmt.Errorf("gs url must begin with 'gs://', instead have, %s", gsURL)
	}

	u, err := url.Parse(gsURL)
	if err != nil {
		return "", fmt.Errorf("unable to parse url, %w", err)
	}

	// Host corresponds to bucket
	// Path corresponds to object
	return path.Join(u.Host, u.Path), nil
}

// ForceReconnect attempts to reconnect to the DUT
func (s *DutServiceServer) ForceReconnect(ctx context.Context, req *api.ForceReconnectRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.ForceReconnectRequest: ", req)

	op := s.manager.NewOperation()

	if err := s.reconnect(ctx); err != nil {
		return nil, err
	}
	s.manager.SetResult(op.Name, &api.CacheResponse{
		Result: &api.CacheResponse_Success_{},
	})

	return op, nil
}

// reconnect starts a new ssh client connection
func (s *DutServiceServer) reconnect(ctx context.Context) error {
	s.logger.Printf("attempting to reconnect to DUT.")
	conn, err := GetConnection(ctx, s.dutName, s.wiringAddress, s.logger)
	if err != nil {
		s.logger.Printf("Failed to reconnect to DUT.")
		return err
	}
	s.connection = &dutssh.SSHClient{Client: conn}
	return nil
}

// readFetchCrashesProto reads stdout and transforms it into a FetchCrashesResponse
func readFetchCrashesProto(stdout io.Reader, buffer bytes.Buffer) (*api.FetchCrashesResponse, error) {
	var sizeBytes [8]byte
	crashResp := &api.FetchCrashesResponse{}

	buffer.Reset()

	// First, read the length of the proto.
	length, err := io.ReadFull(stdout, sizeBytes[:])
	if err != nil {
		if length == 0 && err == io.EOF {
			// We've come to the end of the stream -- expected condition.
			return nil, nil
		}
		// Read only a partial int. Abort.
		return nil, status.Errorf(codes.Unavailable, "Failed to read a size: %s", err.Error())
	}
	size := binary.BigEndian.Uint64(sizeBytes[:])

	// Next, read the actual proto and parse it.
	if length, err := io.CopyN(&buffer, stdout, int64(size)); err != nil {
		return nil, status.Errorf(codes.Unavailable, "Failed to read complete proto. Read %d bytes but wanted %d. err: %s", length, size, err)
	}
	// CopyN guarantees that n == protoByes.Len() == size now.

	if err := proto.Unmarshal(buffer.Bytes(), crashResp); err != nil {
		return nil, status.Errorf(codes.Internal, "Failed to unmarshal proto: %s; %v", err.Error(), buffer.Bytes())
	}

	return crashResp, nil
}

// GetConnectionWithRetry calls GetConnect with retries.
func GetConnectionWithRetry(ctx context.Context, dutIdentifier string, wiringAddress string, req *api.RestartRequest, logger *log.Logger) (*ssh.Client, error) {
	logger.Printf("GetConnectionWithRetry Start")

	retryCount := 5
	retryInterval := time.Duration(10 * time.Second)
	var err error
	var client *ssh.Client
	if req.Retry != nil {
		retryCount = int(req.Retry.Times)
		retryInterval = time.Duration(req.Retry.IntervalMs) * time.Millisecond
	}
	logger.Printf("GetConnectionWithRetry Retries %v Interval %v", retryCount, retryInterval)

	for ; retryCount >= 0; retryCount-- {
		err = nil
		logger.Printf("GetConnectionWithRetry Calling GetConn!")

		client, err = GetConnection(ctx, dutIdentifier, wiringAddress, logger)
		if err == nil {
			logger.Printf("GetConnectionWithRetry succeed with %d retries left.\n", retryCount)
			return client, nil
		} else {
			logger.Printf("GetConnectionWithRetry FAILED TO CONNECT TO DUT %s", err)
		}
		time.Sleep(retryInterval)
	}
	logger.Printf("GetConnectionWithRetry failed after exhausting retries.\n")
	return nil, err
}

// GetConnection connects to a dut server. If wiringAddress is provided,
// it resolves the dut name to ip address; otherwise, uses dutIdentifier as is.
func GetConnection(ctx context.Context, dutIdentifier string, wiringAddress string, logger *log.Logger) (*ssh.Client, error) {
	logger.Printf("GetConnection Start!")

	var addr string
	logger.Printf("GetConnection wiringAddress: %s", wiringAddress)

	if wiringAddress != "" {
		var err error
		logger.Printf("GetConnection Calling GetSSHADDR!")

		addr, err = dutssh.GetSSHAddr(ctx, dutIdentifier, wiringAddress)
		if err != nil {
			logger.Printf("GetConnection FAILED GetSSHADDR!")

			return nil, err
		}
	} else {
		logger.Printf("GetConnection dutIdentifier: %s", dutIdentifier)

		addr = dutIdentifier
	}
	logger.Printf("GetConnection Attempting to Dial!")
	ssh, err := ssh.Dial("tcp", addr, dutssh.GetSSHConfig())
	logger.Printf("GetConnection FINISHED Dial! %s\n", err)

	return ssh, err
}

// runCmd run remote command returning return value, stdout, stderr, and error if any
func (s *DutServiceServer) runCmd(cmd string, stdin io.Reader, combined bool) *api.ExecCommandResponse {
	s.logger.Printf("Running cmd %s", cmd)

	s.logger.Printf("Checking Connection")
	if !s.connection.IsAlive() {
		s.logger.Printf("Connection is not alive, trying to reconnect")
		if err := s.reconnect(context.Background()); err != nil {
			s.logger.Printf("failed to reconnect in runcmd %s\n", err)

			return &api.ExecCommandResponse{
				ExitInfo: createFailedToStartExitInfo(err, s.logger),
			}
		}
	}
	s.logger.Printf("Connection check complete.")

	session, err := s.connection.NewSession()
	if err != nil {
		s.logger.Printf("failed to start session %s\n", err)
		return &api.ExecCommandResponse{
			ExitInfo: createFailedToStartExitInfo(err, s.logger),
		}
	}
	defer session.Close()

	var stdOut bytes.Buffer
	var stdErr bytes.Buffer

	if stdin != nil {
		session.SetStdin(stdin)
	}
	session.SetStdout(&stdOut)
	if !combined {
		session.SetStderr(&stdErr)
	} else {
		session.SetStderr(&stdOut)
	}
	err = session.Run(cmd)

	return &api.ExecCommandResponse{
		Stdout:   stdOut.Bytes(),
		Stderr:   stdErr.Bytes(),
		ExitInfo: getExitInfo(err, s.logger),
	}
}

// runCmdOutput interprets the given string command in a shell and returns stdout and stderr.
// Overall this is a simplified version of runCmd which only returns output.
func (s *DutServiceServer) runCmdOutput(cmd string) (string, string, error) {
	s.logger.Printf("Checking Connection is alive.")
	if !s.connection.IsAlive() {
		if err := s.reconnect(context.Background()); err != nil {
			return "", "", fmt.Errorf("failed to reconnect after connection failure, %s", err)
		}
	}
	s.logger.Printf("Checking Connection complete.")

	s.logger.Printf("Creating new session.")
	session, err := s.connection.NewSession()
	if err != nil {
		return "", "", fmt.Errorf("failed to establish a new session for command run, %s", err)
	}
	var stdOut bytes.Buffer
	var stdErr bytes.Buffer

	session.SetStdout(&stdOut)
	session.SetStderr(&stdErr)

	err = session.Run(cmd)
	defer session.Close()
	return stdOut.String(), stdErr.String(), err
}

// getExitInfo extracts exit info from Session Run's error
func getExitInfo(runError error, logger *log.Logger) *api.ExecCommandResponse_ExitInfo {
	// If no error, command succeeded
	if runError == nil {
		logger.Println("NO RUN ISSSUES")

		return createCommandSucceededExitInfo()
	}

	// If ExitError, command ran but did not succeed
	var ee *ssh.ExitError
	if errors.As(runError, &ee) {
		logger.Println("cmdfailed")

		return createCommandFailedExitInfo(ee)
	}

	// Otherwise we assume command failed to start
	return createFailedToStartExitInfo(runError, logger)
}

func createFailedToStartExitInfo(err error, logger *log.Logger) *api.ExecCommandResponse_ExitInfo {
	logger.Println("runError Failed to start exit")

	return &api.ExecCommandResponse_ExitInfo{
		Status:       42, // Contract dictates arbitrary response, thus 42 is as good as any number
		Signaled:     false,
		Started:      false,
		ErrorMessage: err.Error(),
	}
}

func createCommandSucceededExitInfo() *api.ExecCommandResponse_ExitInfo {
	return &api.ExecCommandResponse_ExitInfo{
		Status:       0,
		Signaled:     false,
		Started:      true,
		ErrorMessage: "",
	}
}

func createCommandFailedExitInfo(err *ssh.ExitError) *api.ExecCommandResponse_ExitInfo {
	return &api.ExecCommandResponse_ExitInfo{
		Status:       int32(err.ExitStatus()),
		Signaled:     true,
		Started:      true,
		ErrorMessage: "",
	}
}

// getPipes returns stdout and stderr from a Session/SessionInterface. stderr is
// converted to a buffer do to concurrency expectations
func getPipes(s dutssh.SessionInterface) (io.Reader, *bufio.Scanner, error) {
	stdout, err := s.StdoutPipe()
	if err != nil {
		return nil, nil, status.Errorf(codes.FailedPrecondition, "Failed to get stdout: %s", err)
	}

	stderrReader, err := s.StderrPipe()
	if err != nil {
		return nil, nil, status.Errorf(codes.FailedPrecondition, "Failed to get stderr: %s", err)
	}
	stderr := bufio.NewScanner(stderrReader)

	return stdout, stderr, nil
}
