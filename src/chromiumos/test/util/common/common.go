// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"context"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"os"
	"os/exec"
	"path/filepath"

	"go.chromium.org/chromiumos/config/go/test/api"
)

// RunCmd runs a command in a remote DUT via DutServiceClient.
func RunCmd(ctx context.Context, cmd string, args []string, dut api.DutServiceClient) (string, error) {
	log.Printf("<post-process> Run cmd: %s, %s\n", cmd, args)
	req := api.ExecCommandRequest{
		Command: cmd,
		Args:    args,
		Stdout:  api.Output_OUTPUT_PIPE,
		Stderr:  api.Output_OUTPUT_PIPE,
	}
	stream, err := dut.ExecCommand(ctx, &req)
	if err != nil {
		log.Printf("<cros-provision> Run cmd FAILED: %s\n", err)
		return "", fmt.Errorf("execution fail: %w", err)
	}
	// Expecting single stream result
	execCmdResponse, err := stream.Recv()
	if err != nil {
		return "", fmt.Errorf("execution single stream result: %w", err)
	}
	if execCmdResponse.ExitInfo.Status != 0 {
		err = fmt.Errorf("status:%v message:%v", execCmdResponse.ExitInfo.Status, execCmdResponse.ExitInfo.ErrorMessage)
	}
	if string(execCmdResponse.Stderr) != "" {
		log.Printf("<post-process> execution finished with stderr: %s\n", string(execCmdResponse.Stderr))
	}
	return string(execCmdResponse.Stdout), err
}

// GetFile gets a file from a remote DUT via DutServiceClient.
func GetFile(ctx context.Context, file string, dut api.DutServiceClient) (string, error) {
	_, fileName := filepath.Split(file)

	gf := FetchFile{
		ctx:       ctx,
		file:      file,
		dutClient: dut,
		fileName:  fileName,
		destDir:   "/var/tmp/outputResult/",
	}
	return gf.getFile()

}

// FetchFile is a helper struct for GetFile.
type FetchFile struct {
	ctx         context.Context
	file        string
	fileName    string
	destDir     string
	tmpdir      string
	tarFileName string
	outputF     *os.File
	dutClient   api.DutServiceClient
}

func (f *FetchFile) getFile() (string, error) {
	log.Printf("Running GetFile cmd: %s\n", f.file)
	req := api.FetchFileRequest{
		File: f.file,
	}
	stream, err := f.dutClient.FetchFile(f.ctx, &req)
	if err != nil {
		log.Printf("GetFile: Fetch cmd failed: %s\n", err)
		return "", fmt.Errorf("FETCH fail: %w", err)
	}

	err = f.makeOutputTmpFile()
	if err != nil {
		log.Printf("Unable to make temp file: %s", err)

		return "", fmt.Errorf("Unable to make temp file: %s", err)
	}

	err = f.readStream(stream)
	if err != nil {
		log.Printf("Reading stream err: %s", err)
		return "", fmt.Errorf("Read Stream err: %s", err)
	}

	return f.untarContents()
}

func (f *FetchFile) makeOutputTmpFile() error {
	tmpDir, err := ioutil.TempDir("", "")
	if err != nil {
		return fmt.Errorf("GetFile: Failed to create local tmpdir: %q, err :%s", tmpDir, err)
	}
	f.tmpdir = tmpDir
	tarName := fmt.Sprintf("%s.tar.bz", f.fileName)
	f.tarFileName = filepath.Join(tmpDir, tarName)
	tarFile, err := os.Create(f.tarFileName)
	f.outputF = tarFile
	return nil
}

func (f *FetchFile) readStream(stream api.DutService_FetchFileClient) error {
	defer f.outputF.Close()

	for {
		resp, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			log.Printf("GetFile: Failure in stream fetch: %s", err)
			return err
		}
		// Maybe eed ...
		f.outputF.Write(resp.File)
	}
	return nil
}

func (f *FetchFile) untarContents() (string, error) {
	lCmd := exec.CommandContext(f.ctx, "tar", "-xvf", f.tarFileName, "-C", f.destDir)
	if err := lCmd.Run(); err != nil {
		log.Printf("writeStreamToFile: Unable to untar file: %s %s %s %s", err, lCmd.Stdout, lCmd.Stderr, f.tarFileName)
		return "", fmt.Errorf("writeStreamToFile: Unable to untar file: %s", err)
	}
	log.Printf("Successful pull! Content located @: %s", filepath.Join(f.destDir, f.fileName))
	os.RemoveAll(f.tmpdir)

	return filepath.Join(f.destDir, f.fileName), nil
}
