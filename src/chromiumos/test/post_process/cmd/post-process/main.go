// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the post-process for finding tests based on tags.
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"path/filepath"
	"time"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"

	"chromiumos/test/post_process/cmd/post-process/commands"
	"chromiumos/test/post_process/cmd/post-process/common"
)

const (
	defaultRootPath        = "/tmp/test/post-process"
	defaultInputFileName   = "request.json"
	defaultOutputFileName  = "result.json"
	defaultTestMetadataDir = "/tmp/test/metadata"
)

// Version is the version info of this command. It is filled in during emerge.
var Version = "<unknown>"
var defaultPort = 8010

type args struct {
	// Common input params.
	logPath   string
	inputPath string
	output    string
	version   bool

	// Server mode params
	port        int
	dutendpoint string
}

func parseAndRunCmds(req *api.RunActivityRequest, log *log.Logger, dutClient api.DutServiceClient) (*api.RunActivityResponse, error) {
	log.Println("Start parse")

	switch op := req.Request.(type) {
	case *api.RunActivityRequest_GetFwInfoRequest:
		log.Println("GettingFWInfo Task")

		cmdResp, err := commands.GetFwInfo(log, op.GetFwInfoRequest, dutClient)
		resp := api.RunActivityResponse{
			Response: &api.RunActivityResponse_GetFwInfoResponse{
				GetFwInfoResponse: cmdResp,
			},
		}
		return &resp, err
	case *api.RunActivityRequest_GetFilesFromDutRequest:
		log.Println("GetFilesFromDut Task")
		_, err := commands.GetFilesFromDUT(log, op.GetFilesFromDutRequest, dutClient)

		return nil, err
	default:
		log.Println("None")
		return nil, fmt.Errorf("can only be one of registered types")
	}

}

// startServer is the entry point for running post-process (TestFinderService) in server mode.
func startServer(d []string) int {
	a := args{}
	t := time.Now()
	defaultLogPath := filepath.Join(defaultRootPath, t.Format("20060102-150405"))
	fs := flag.NewFlagSet("Run post-process", flag.ExitOnError)
	fs.StringVar(&a.logPath, "log", defaultLogPath, fmt.Sprintf("Path to record finder logs. Default value is %s", defaultLogPath))
	fs.IntVar(&a.port, "port", defaultPort, fmt.Sprintf("Specify the port for the server. Default value %d.", defaultPort))
	fs.StringVar(&a.dutendpoint, "dutendpoint", "", fmt.Sprintf("Specify the endpoint for the running dut-service in the form of ip:port"))

	fs.Parse(d)

	logFile, err := common.CreateLogFile(a.logPath)
	if err != nil {
		log.Fatalln("Failed to create log file", err)
		return 2
	}
	defer logFile.Close()

	logger := common.NewLogger(logFile)

	if a.dutendpoint == "" {
		log.Fatalln("need dut-server endpoint")
		return 2
	}
	dutAddr := a.dutendpoint

	dutConn, err := grpc.Dial(dutAddr, grpc.WithInsecure())
	defer dutConn.Close()
	dutClient := api.NewDutServiceClient(dutConn)

	l, err := net.Listen("tcp", fmt.Sprintf(":%d", a.port))
	if err != nil {
		logger.Fatalln("Failed to create a net listener: ", err)
		return 2
	}
	logger.Println("Starting TestFinderService on port ", a.port)

	if err != nil {
		log.Printf("DutConn Failed!")
		return 2
	}
	log.Printf("Dut Conn Established")

	server, closer := NewServer(logger, dutClient)
	defer closer()
	err = server.Serve(l)
	if err != nil {
		logger.Fatalln("Failed to initialize server: ", err)
		return 2
	}
	return 0
}

func mainInternal(ctx context.Context) int {
	return startServer(os.Args[2:])

}

func main() {
	os.Exit(mainInternal(context.Background()))
}
