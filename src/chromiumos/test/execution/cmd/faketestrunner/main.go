// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the tast_rtd executable, used to invoke tast in RTD.
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"os/exec"
	"time"

	"github.com/golang/protobuf/ptypes"
	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// runTestExec will run testexecserver.
func runTestExec(logger *log.Logger, serverPort int, driver string, req *api.RunTestsRequest) (*exec.Cmd, error) {
	// Run testexecserver
	const path = "/usr/bin/testexecserver"
	cmd := exec.Command(path, "-port", fmt.Sprintf("%d", serverPort), "-driver", driver)
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return nil, err
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	if err := cmd.Start(); err != nil {
		return nil, err
	}

	go func() {
		scanner := bufio.NewScanner(stderr)
		for scanner.Scan() {
			logger.Printf("[testexecserver] %v", scanner.Text())
		}
	}()

	go func() {
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			logger.Printf("[testexecserver] %v", scanner.Text())
		}
	}()

	return cmd, nil
}

// readInput reads an execution_service json file and returns a pointer to RunTestsRequest.
func readInput(fileName string) (*api.RunTestsRequest, error) {
	data, err := ioutil.ReadFile(fileName)
	if err != nil {
		return nil, fmt.Errorf("fail to read file %v: %v", fileName, err)
	}
	req := api.RunTestsRequest{}
	if err = json.Unmarshal(data, &req); err != nil {
		return nil, fmt.Errorf("fail to unmarshal file %v: %v", fileName, err)
	}
	return &req, nil
}

// sendRunRequest sends run request to the test execution server.
func sendRunRequest(serverPort int, req *api.RunTestsRequest, output string) (err error) {
	// Set up connection with ProgressSink
	addr := fmt.Sprintf("localhost:%d", serverPort)
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Minute) // one hour time for now.
	defer cancel()
	conn, err := grpc.DialContext(ctx, addr, grpc.WithBlock(), grpc.WithInsecure())
	if err != nil {
		return fmt.Errorf("failed to connect to the test execution server: %v", err)
	}
	defer conn.Close()
	client := api.NewExecutionServiceClient(conn)
	// TODO: handle response in next CL
	op, err := client.RunTests(ctx, req)
	if err != nil {
		st, ok := status.FromError(err)
		if !ok {
			return fmt.Errorf("failed to get status code: %v", err)
		}
		if st.Code() == codes.NotFound {
			return fmt.Errorf("Unknown status code:, %v", st.Code())
		}
		return fmt.Errorf("failed to call RunTests(%v): %v", req, err)
	}

	opCli := longrunning.NewOperationsClient(conn)
	op, err = opCli.WaitOperation(ctx, &longrunning.WaitOperationRequest{
		Name: op.GetName(),
	})
	if err != nil {
		return fmt.Errorf("failed to wait operation: %v", err)
	}
	if !op.GetDone() {
		return fmt.Errorf("WaitOperation timed out (%v)", op)
	}

	if output == "" {
		output = "output.json"
	}
	resp := &api.RunTestsResponse{}
	if err := ptypes.UnmarshalAny(op.GetResponse(), resp); err != nil {
		return fmt.Errorf("failed to unmarshall response: %v", err)
	}
	buf, err := json.MarshalIndent(resp, "", " ")
	if err != nil {
		return fmt.Errorf("failed to marshall response to a json string: %v", err)
	}
	if err := ioutil.WriteFile(output, buf, 0644); err != nil {
		return fmt.Errorf("failed to write to json file: %v", err)
	}
	return nil
}

func main() {
	os.Exit(func() int {
		input := flag.String("input", "", "specify the test execution request json input file")
		output := flag.String("output", "", "specify the test execution request json output file")
		serverPort := flag.Int("testexecserver_port", 0, "specify the port number to start test execution server.")
		// TODO: Use it as a temporary flag to help development. Will be removed after metadata support.
		driver := flag.String("driver", "tast", "specify a driver (tast/tauto) to be used.")
		flag.Parse()

		logger := log.New(os.Stderr, "", 0)
		req, err := readInput(*input)
		if err != nil {
			logger.Printf("Failed to read test executation json file %v: %v", *input, err)
			return 1
		}
		cmd, err := runTestExec(logger, *serverPort, *driver, req)
		if err != nil {
			logger.Printf("Failed to invoke testexecserver: %v", err)
			return 1
		}
		if err := sendRunRequest(*serverPort, req, *output); err != nil {
			logger.Printf("Failed to send test executation request: %v", err)
			return 1
		}
		if err := cmd.Process.Kill(); err != nil {
			logger.Printf("Failed to kill testexecserver process: %v", err)
			return 1
		}
		cmd.Wait()

		return 0
	}())
}
