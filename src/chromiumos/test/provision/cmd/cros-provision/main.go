// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the cros-provision used to setup CrOS devices.
package main

import (
	"chromiumos/test/provision/cmd/provisionserver"
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"strings"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
	"go.chromium.org/luci/common/errors"
)

const (
	// version is the version info of this command. It is filled in during emerge.
	version         = "<unknown>"
	helpDescription = `cros-provision tool

The tool is allow to perform provision ChromeOS devices.
Please read go/cros-provision-f20 for mode details.

Commands:
  cli       Running provision in CLI mode result will be printed to output file. Mostly used to prepare
            device before running tests.
            usage: cros-provision cli -input input_file -output output_file [-log-path /tmp/provision/]

  server    Starting server and allow work with server by RPC calls. Mostly used for tests.
            usage: cros-provision server -input input_file [-log-path /tmp/provision/] [-port 80]

  -version  Print version of lib.
  -help     Print this help.`
	defaultLogDirectory = "/tmp/provision/"
	defaultPort         = 80
)

// createLogFile creates a file and its parent directory for logging purpose.
func createLogFile(dir string) (*os.File, error) {
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create directory %v: %v", dir, err)
	}
	logFilePath := filepath.Join(dir, "log.txt")
	// Log the full output of the command to disk.
	logFile, err := os.Create(logFilePath)
	if err != nil {
		return nil, fmt.Errorf("failed to create file %v: %v", logFilePath, err)
	}
	return logFile, nil
}

// newLogger creates a logger. Using go default logger for now.
func newLogger(logFile *os.File) *log.Logger {
	mw := io.MultiWriter(logFile, os.Stderr)
	return log.New(mw, "", log.LstdFlags|log.LUTC)
}

type args struct {
	// Common input params.
	logPath    string
	inputPath  string
	outputPath string

	// Server mode params
	port int
}

func (a args) validate(expectProvisionState bool) (*api.CrosProvisionRequest, error) {
	if a.inputPath == "" {
		return nil, errors.Reason("input file not specified").Err()
	}
	if a.outputPath == "" {
		return nil, errors.Reason("output file not specified").Err()
	}

	in, err := readInput(a.inputPath)
	if err != nil {
		return nil, errors.Annotate(err, "fail to read input file").Err()
	}
	if expectProvisionState && in.GetProvisionState() == nil {
		return nil, errors.Reason("provision state was not specified in input file").Err()
	}
	if in.GetDut() == nil || in.GetDut().GetId().GetValue() == "" {
		return nil, errors.Reason("dut id is not specified in input file").Err()
	}
	if isAddressEmpty(in.GetDutServer()) {
		return nil, errors.Reason("dut server address is no specified or incorrect in input file").Err()
	}
	return in, nil
}

// readInput reads input request data from the input file.
func readInput(path string) (*api.CrosProvisionRequest, error) {
	in := &api.CrosProvisionRequest{}
	r, err := os.Open(path)
	if err != nil {
		return nil, errors.Annotate(err, "read input").Err()
	}

	umrsh := jsonpb.Unmarshaler{}
	umrsh.AllowUnknownFields = true
	err = umrsh.Unmarshal(r, in)
	return in, errors.Annotate(err, "read input").Err()
}

func isAddressEmpty(a *lab_api.IpEndpoint) bool {
	return a == nil || a.GetAddress() == "" || a.GetPort() <= 0
}

func getAddress(a *lab_api.IpEndpoint) string {
	return fmt.Sprintf("%s:%d", a.GetAddress(), a.GetPort())
}

func runCLI(ctx context.Context, d []string) int {
	a := args{}
	fs := flag.NewFlagSet("Run provision", flag.ExitOnError)
	fs.StringVar(&a.logPath, "log-path", defaultLogDirectory, fmt.Sprintf("Path to record execution logs. Default value is %s", defaultLogDirectory))
	fs.StringVar(&a.inputPath, "input", "", "Specify the request jsonproto input file. Provide service paths and ProvisionState.")
	fs.StringVar(&a.outputPath, "output", "", "Specify the response jsonproto output file. Empty placeholder file to provide result from provisioning the DUT.")
	fs.Parse(d)

	logFile, err := createLogFile(a.logPath)
	if err != nil {
		log.Fatalln("Failed to create log file", err)
		return 2
	}
	defer logFile.Close()
	logger := newLogger(logFile)
	in, err := a.validate(true)
	if err != nil {
		log.Fatalf("Validate input fail: %s", err)
		return 2
	}
	p, closer, err := provisionserver.NewProvision(logger, in.GetDut(), getAddress(in.GetDutServer()))
	defer closer()
	if err != nil {
		logger.Fatalln("Failed to create provision: ", err)
		return 2
	}
	if err := p.RunCLI(ctx, in.GetProvisionState(), a.outputPath); err != nil {
		logger.Fatalln("Failed to perform provision: ", err)
		return 1
	}
	return 0
}

func startServer(d []string) int {
	a := args{}
	fs := flag.NewFlagSet("Start provision server", flag.ExitOnError)
	fs.StringVar(&a.logPath, "log-path", defaultLogDirectory, fmt.Sprintf("Path to record execution logs. Default value is %s", defaultLogDirectory))
	fs.StringVar(&a.inputPath, "input", "", "Specify the request jsonproto input file. Provide service paths and ProvisionState.")
	fs.IntVar(&a.port, "port", defaultPort, fmt.Sprintf("Specify the port for the server. Default value %d.", defaultPort))
	fs.Parse(d)

	logFile, err := createLogFile(a.logPath)
	if err != nil {
		log.Fatalln("Failed to create log file", err)
		return 2
	}
	defer logFile.Close()
	logger := newLogger(logFile)
	in, err := a.validate(false)
	if err != nil {
		log.Fatalf("Validate input fail: %s", err)
		return 2
	}
	p, closer, err := provisionserver.NewProvision(logger, in.GetDut(), getAddress(in.GetDutServer()))
	defer closer()
	if err != nil {
		logger.Fatalln("Failed to create provision: ", err)
		return 2
	}
	if err := p.StartServer(a.port); err != nil {
		logger.Fatalln("Failed to perform provision: ", err)
		return 1
	}
	return 0
}

// Specify run mode for CLI.
type runMode string

const (
	runCli     runMode = "cli"
	runServer  runMode = "server"
	runVersion runMode = "version"
	runHelp    runMode = "help"
)

func getRunMode() (runMode, error) {
	if len(os.Args) > 1 {
		for _, a := range os.Args {
			if a == "-version" {
				return runVersion, nil
			}
		}
		switch strings.ToLower(os.Args[1]) {
		case "cli":
			return runCli, nil
		case "server":
			return runServer, nil
		}
	}
	// If we did not find special run mode then just print help for user.
	return runHelp, nil
}

func mainInternal(ctx context.Context) int {
	rm, err := getRunMode()
	if err != nil {
		log.Fatalln(err)
		return 2
	}
	switch rm {
	case runCli:
		log.Printf("Running CLI mode!")
		return runCLI(ctx, os.Args[2:])
	case runServer:
		log.Printf("Running server mode!")
		return startServer(os.Args[2:])
	case runVersion:
		log.Printf("cros-provisions version: %s", version)
		return 0
	}
	log.Printf(helpDescription)
	return 0
}

func main() {
	os.Exit(mainInternal(context.Background()))
}
