// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"chromiumos/test/dut/cmd/dutserver/dutssh"
	"context"
	"errors"
	"io"
	"log"
	"net"
	"strings"
	"testing"

	"go.chromium.org/chromiumos/config/go/test/api"
	"golang.org/x/crypto/ssh"
	"google.golang.org/grpc"
)

type MockSession_Success struct {
	Stdout io.Writer
	Stderr io.Writer
}

func (s *MockSession_Success) Close() error {
	return nil
}
func (s *MockSession_Success) SetStdout(writer io.Writer) {
	s.Stdout = writer
}
func (s *MockSession_Success) SetStderr(writer io.Writer) {
	s.Stderr = writer
}

func (s *MockSession_Success) Start(cmd string) error {
	return nil
}

func (s *MockSession_Success) Output(cmd string) ([]byte, error) {
	return nil, nil
}

func (s *MockSession_Success) StdoutPipe() (io.Reader, error) {
	return nil, nil
}

func (s *MockSession_Success) StderrPipe() (io.Reader, error) {
	return nil, nil
}

func (s *MockSession_Success) Run(cmd string) error {
	s.Stdout.Write([]byte("success!"))
	s.Stderr.Write([]byte("not failed!"))
	return nil
}

type MockConnection_Success struct{}

func (c *MockConnection_Success) Close() error {
	return nil
}

func (c *MockConnection_Success) NewSession() (dutssh.SessionInterface, error) {
	return &MockSession_Success{}, nil
}

// Tests if DutServiceServer can handle empty request without problem.
func TestDutServiceServer_Empty(t *testing.T) {
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	dutConn := &MockConnection_Success{}
	srv := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), dutConn, "", 0)
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	if _, err := cl.ExecCommand(ctx, &api.ExecCommandRequest{}); err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}
}

// Tests that a command executes successfully
func TestDutServiceServer_CommandWorks(t *testing.T) {
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	dutConn := &MockConnection_Success{}
	srv := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), dutConn, "", 0)
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.ExecCommand(ctx, &api.ExecCommandRequest{})
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	resp := &api.ExecCommandResponse{}
	err = stream.RecvMsg(resp)
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	if resp.ExitInfo.Status != 0 {
		t.Fatalf("Expecting return type to be 0, instead got: %v", resp.ExitInfo.Status)
	}

	if string(resp.Stderr) != "not failed!" {
		t.Fatalf("Expecting stderr to be \"not failed\", instead got %v", string(resp.Stderr))
	}

	if string(resp.Stdout) != "success!" {
		t.Fatalf("Expecting stderr to be \"success\", instead got %v", string(resp.Stderr))
	}

	if resp.ExitInfo.Signaled {
		t.Fatalf("Signalled should not be set!")
	}

	if !resp.ExitInfo.Started {
		t.Fatalf("Started should be set!")
	}
}

type MockSession_CommandFailed struct {
	Stdout io.Writer
	Stderr io.Writer
}

func (s *MockSession_CommandFailed) Close() error {
	return nil
}
func (s *MockSession_CommandFailed) SetStdout(writer io.Writer) {
	s.Stdout = writer
}
func (s *MockSession_CommandFailed) SetStderr(writer io.Writer) {
	s.Stderr = writer
}

func (s *MockSession_CommandFailed) Run(cmd string) error {
	s.Stdout.Write([]byte("not success!"))
	s.Stderr.Write([]byte("failure!"))
	wm := ssh.Waitmsg{}
	return &ssh.ExitError{
		Waitmsg: wm,
	}
}

func (s *MockSession_CommandFailed) Start(cmd string) error {
	return nil
}

func (s *MockSession_CommandFailed) Output(cmd string) ([]byte, error) {
	return nil, nil
}

func (s *MockSession_CommandFailed) StdoutPipe() (io.Reader, error) {
	return nil, nil
}

func (s *MockSession_CommandFailed) StderrPipe() (io.Reader, error) {
	return nil, nil
}

type MockConnection_CommandFailed struct{}

func (c *MockConnection_CommandFailed) Close() error {
	return nil
}

func (c *MockConnection_CommandFailed) NewSession() (dutssh.SessionInterface, error) {
	return &MockSession_CommandFailed{}, nil
}

// Tests that a command does not execute successfully
func TestDutServiceServer_CommandFails(t *testing.T) {
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	dutConn := &MockConnection_CommandFailed{}
	srv := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), dutConn, "", 0)
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.ExecCommand(ctx, &api.ExecCommandRequest{})
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	resp := &api.ExecCommandResponse{}
	err = stream.RecvMsg(resp)
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	if string(resp.Stderr) != "failure!" {
		t.Fatalf("Expecting stderr to be \"not success\", instead got %v", string(resp.Stderr))
	}

	if string(resp.Stdout) != "not success!" {
		t.Fatalf("Expecting stderr to be \"failure\", instead got %v", string(resp.Stderr))
	}

	if !resp.ExitInfo.Signaled {
		t.Fatalf("Signalled should be set!")
	}

	if !resp.ExitInfo.Started {
		t.Fatalf("Started should be set!")
	}
}

type MockSession_PreCommandFailure struct {
	Stdout io.Writer
	Stderr io.Writer
}

func (s *MockSession_PreCommandFailure) Close() error {
	return nil
}
func (s *MockSession_PreCommandFailure) SetStdout(writer io.Writer) {
	s.Stdout = writer
}
func (s *MockSession_PreCommandFailure) SetStderr(writer io.Writer) {
	s.Stderr = writer
}

func (s *MockSession_PreCommandFailure) Run(cmd string) error {
	s.Stdout.Write([]byte(""))
	s.Stderr.Write([]byte(""))
	return &ssh.ExitMissingError{}
}

func (s *MockSession_PreCommandFailure) Start(cmd string) error {
	return nil
}

func (s *MockSession_PreCommandFailure) Output(cmd string) ([]byte, error) {
	return nil, nil
}

func (s *MockSession_PreCommandFailure) StdoutPipe() (io.Reader, error) {
	return nil, nil
}

func (s *MockSession_PreCommandFailure) StderrPipe() (io.Reader, error) {
	return nil, nil
}

type MockConnection_PreCommandFailure struct{}

func (c *MockConnection_PreCommandFailure) Close() error {
	return nil
}

func (c *MockConnection_PreCommandFailure) NewSession() (dutssh.SessionInterface, error) {
	return &MockSession_PreCommandFailure{}, nil
}

// Tests that a command does not execute
func TestDutServiceServer_PreCommandFails(t *testing.T) {
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	dutConn := &MockConnection_PreCommandFailure{}
	srv := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), dutConn, "", 0)
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.ExecCommand(ctx, &api.ExecCommandRequest{})
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	resp := &api.ExecCommandResponse{}
	err = stream.RecvMsg(resp)
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	if string(resp.Stderr) != "" {
		t.Fatalf("Expecting stderr to be empty, instead got %v", string(resp.Stderr))
	}

	if string(resp.Stdout) != "" {
		t.Fatalf("Expecting stderr to be empty, instead got %v", string(resp.Stderr))
	}

	if resp.ExitInfo.Signaled {
		t.Fatalf("Signalled should not be set!")
	}

	if resp.ExitInfo.Started {
		t.Fatalf("Started should not be set!")
	}
}

type MockConnection_NewSessionFailure struct{}

func (c *MockConnection_NewSessionFailure) Close() error {
	return nil
}

func (c *MockConnection_NewSessionFailure) NewSession() (dutssh.SessionInterface, error) {
	return nil, errors.New("Session failed.")
}

// Tests that a session fails
func TestDutServiceServer_NewSessionFails(t *testing.T) {
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	dutConn := &MockConnection_NewSessionFailure{}
	srv := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), dutConn, "", 0)
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.ExecCommand(ctx, &api.ExecCommandRequest{})
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	resp := &api.ExecCommandResponse{}
	err = stream.RecvMsg(resp)
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	if string(resp.Stderr) != "" {
		t.Fatalf("Expecting stderr to be empty, instead got %v", string(resp.Stderr))
	}

	if string(resp.Stdout) != "" {
		t.Fatalf("Expecting stderr to be empty, instead got %v", string(resp.Stderr))
	}

	if resp.ExitInfo.Signaled {
		t.Fatalf("Signalled should not be set!")
	}

	if resp.ExitInfo.Started {
		t.Fatalf("Started should not be set!")
	}

	if resp.ExitInfo.ErrorMessage != "Session failed." {
		t.Fatalf("Error message should be session failed, instead got %v", resp.ExitInfo.ErrorMessage)
	}
}

type MockSession_FetchCrashesPathExistsFailure struct {
}

func (s *MockSession_FetchCrashesPathExistsFailure) Close() error {
	return nil
}
func (s *MockSession_FetchCrashesPathExistsFailure) SetStdout(writer io.Writer) {
}
func (s *MockSession_FetchCrashesPathExistsFailure) SetStderr(writer io.Writer) {
}

func (s *MockSession_FetchCrashesPathExistsFailure) Start(cmd string) error {
	return nil
}

func (s *MockSession_FetchCrashesPathExistsFailure) Output(cmd string) ([]byte, error) {
	return nil, errors.New("command failed!")
}

func (s *MockSession_FetchCrashesPathExistsFailure) StdoutPipe() (io.Reader, error) {
	return nil, nil
}

func (s *MockSession_FetchCrashesPathExistsFailure) StderrPipe() (io.Reader, error) {
	return nil, nil
}

func (s *MockSession_FetchCrashesPathExistsFailure) Run(cmd string) error {
	return nil
}

type MockConnection_FetchCrashesPathExistsFailure struct{}

func (c *MockConnection_FetchCrashesPathExistsFailure) Close() error {
	return nil
}

func (c *MockConnection_FetchCrashesPathExistsFailure) NewSession() (dutssh.SessionInterface, error) {
	return &MockSession_FetchCrashesPathExistsFailure{}, nil
}

// Tests that a path exist command fails
func TestDutServiceServer_FetchCrasesPathExistsFails(t *testing.T) {
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	dutConn := &MockConnection_FetchCrashesPathExistsFailure{}
	srv := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), dutConn, "", 0)
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.FetchCrashes(ctx, &api.FetchCrashesRequest{})
	if err != nil {
		t.Fatalf("Failed at api.FetchCrashes: %v", err)
	}

	resp := &api.FetchCrashesResponse{}
	err = stream.RecvMsg(resp)
	if err.Error() != "rpc error: code = FailedPrecondition desc = Failed to check crash_serializer existence: command failed!" {
		t.Fatalf("Command failure should have caused an error: %v", err)
	}

}

type MockSession_FetchCrashesPathExistsMissing struct {
}

func (s *MockSession_FetchCrashesPathExistsMissing) Close() error {
	return nil
}
func (s *MockSession_FetchCrashesPathExistsMissing) SetStdout(writer io.Writer) {
}
func (s *MockSession_FetchCrashesPathExistsMissing) SetStderr(writer io.Writer) {
}

func (s *MockSession_FetchCrashesPathExistsMissing) Start(cmd string) error {
	return nil
}

func (s *MockSession_FetchCrashesPathExistsMissing) Output(cmd string) ([]byte, error) {
	return []byte("0"), nil
}

func (s *MockSession_FetchCrashesPathExistsMissing) StdoutPipe() (io.Reader, error) {
	return nil, nil
}

func (s *MockSession_FetchCrashesPathExistsMissing) StderrPipe() (io.Reader, error) {
	return nil, nil
}

func (s *MockSession_FetchCrashesPathExistsMissing) Run(cmd string) error {
	return nil
}

type MockConnection_FetchCrashesPathExistsMissing struct{}

func (c *MockConnection_FetchCrashesPathExistsMissing) Close() error {
	return nil
}

func (c *MockConnection_FetchCrashesPathExistsMissing) NewSession() (dutssh.SessionInterface, error) {
	return &MockSession_FetchCrashesPathExistsMissing{}, nil
}

// Tests that a path exist command returns command missing
func TestDutServiceServer_FetchCrasesPathExistsMissing(t *testing.T) {
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	dutConn := &MockConnection_FetchCrashesPathExistsMissing{}
	srv := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), dutConn, "", 0)
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.FetchCrashes(ctx, &api.FetchCrashesRequest{})
	if err != nil {
		t.Fatalf("Failed at api.FetchCrashes: %v", err)
	}

	resp := &api.FetchCrashesResponse{}
	err = stream.RecvMsg(resp)
	if err.Error() != "rpc error: code = NotFound desc = crash_serializer not present on device." {
		t.Fatalf("Path missing should have caused an error: %v", err)
	}

}

type MockConnection_FetchCrashesNewSessionFailure struct{}

func (c *MockConnection_FetchCrashesNewSessionFailure) Close() error {
	return nil
}

func (c *MockConnection_FetchCrashesNewSessionFailure) NewSession() (dutssh.SessionInterface, error) {
	return nil, errors.New("Session failed.")
}

// Tests that a new session failure fails
func TestDutServiceServer_FetchCrasesNewSessionFailure(t *testing.T) {
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	dutConn := &MockConnection_FetchCrashesNewSessionFailure{}
	srv := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), dutConn, "", 0)
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.FetchCrashes(ctx, &api.FetchCrashesRequest{})
	if err != nil {
		t.Fatalf("Failed at api.FetchCrashes: %v", err)
	}

	resp := &api.FetchCrashesResponse{}
	err = stream.RecvMsg(resp)
	if err.Error() != "rpc error: code = FailedPrecondition desc = Failed to check crash_serializer existence: Session failed." {
		t.Fatalf("Session Failure should have failed: %v", err)
	}

}

type MockSession_FetchCrashesSessionStartFailure struct {
}

func (s *MockSession_FetchCrashesSessionStartFailure) Close() error {
	return nil
}
func (s *MockSession_FetchCrashesSessionStartFailure) SetStdout(writer io.Writer) {
}
func (s *MockSession_FetchCrashesSessionStartFailure) SetStderr(writer io.Writer) {
}

func (s *MockSession_FetchCrashesSessionStartFailure) Start(cmd string) error {
	return errors.New("Session Start Failure.")
}

func (s *MockSession_FetchCrashesSessionStartFailure) Output(cmd string) ([]byte, error) {
	return []byte("1"), nil
}

func (s *MockSession_FetchCrashesSessionStartFailure) StdoutPipe() (io.Reader, error) {
	return strings.NewReader("stdout"), nil
}

func (s *MockSession_FetchCrashesSessionStartFailure) StderrPipe() (io.Reader, error) {
	return strings.NewReader("stderr"), nil
}

func (s *MockSession_FetchCrashesSessionStartFailure) Run(cmd string) error {
	return nil
}

type MockConnection_FetchCrashesSessionStartFailure struct{}

func (c *MockConnection_FetchCrashesSessionStartFailure) Close() error {
	return nil
}

func (c *MockConnection_FetchCrashesSessionStartFailure) NewSession() (dutssh.SessionInterface, error) {
	return &MockSession_FetchCrashesSessionStartFailure{}, nil
}

// Tests that a path exist command returns command missing
func TestDutServiceServer_FetchCrasesSessionStartFailure(t *testing.T) {
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	dutConn := &MockConnection_FetchCrashesSessionStartFailure{}
	srv := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), dutConn, "", 0)
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.FetchCrashes(ctx, &api.FetchCrashesRequest{})
	if err != nil {
		t.Fatalf("Failed at api.FetchCrashes: %v", err)
	}

	resp := &api.FetchCrashesResponse{}
	err = stream.RecvMsg(resp)
	if err.Error() != "rpc error: code = FailedPrecondition desc = Failed to run serializer: Session Start Failure." {
		t.Fatalf("Session Start Failure should have caused an error: %v", err)
	}

}

type MockSession_FetchCrashesPipeFailure struct {
	Stdout io.Writer
	Stderr io.Writer
}

func (s *MockSession_FetchCrashesPipeFailure) Close() error {
	return nil
}
func (s *MockSession_FetchCrashesPipeFailure) SetStdout(writer io.Writer) {
	s.Stdout = writer
}
func (s *MockSession_FetchCrashesPipeFailure) SetStderr(writer io.Writer) {
	s.Stderr = writer
}

func (s *MockSession_FetchCrashesPipeFailure) Start(cmd string) error {
	return nil
}

func (s *MockSession_FetchCrashesPipeFailure) Output(cmd string) ([]byte, error) {
	return []byte("1"), nil
}

func (s *MockSession_FetchCrashesPipeFailure) StdoutPipe() (io.Reader, error) {
	return nil, errors.New("stdout failure.")
}

func (s *MockSession_FetchCrashesPipeFailure) StderrPipe() (io.Reader, error) {
	return nil, nil
}

func (s *MockSession_FetchCrashesPipeFailure) Run(cmd string) error {
	return nil
}

type MockConnection_FetchCrashesPipeFailure struct{}

func (c *MockConnection_FetchCrashesPipeFailure) Close() error {
	return nil
}

func (c *MockConnection_FetchCrashesPipeFailure) NewSession() (dutssh.SessionInterface, error) {
	return &MockSession_FetchCrashesPipeFailure{}, nil
}

// Tests that a path exist command returns command missing
func TestDutServiceServer_FetchCrasesPipeFailure(t *testing.T) {
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	dutConn := &MockConnection_FetchCrashesPipeFailure{}
	srv := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), dutConn, "", 0)
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.FetchCrashes(ctx, &api.FetchCrashesRequest{})
	if err != nil {
		t.Fatalf("Failed at api.FetchCrashes: %v", err)
	}

	resp := &api.FetchCrashesResponse{}
	err = stream.RecvMsg(resp)
	if err.Error() != "rpc error: code = FailedPrecondition desc = Failed to get stdout: stdout failure." {
		t.Fatalf("Standard Out Failure should have caused an error: %v", err)
	}

}
