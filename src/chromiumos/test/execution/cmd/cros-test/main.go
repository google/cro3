// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the executionservice for running tests.
package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"path/filepath"
	"strings"
	"time"

	"chromiumos/test/execution/cmd/cros-test/internal/common"
	"chromiumos/test/execution/errors"
	"chromiumos/test/util/metadata"
	"chromiumos/test/util/portdiscovery"
)

// Version is the version info of this command. It is filled in during emerge.
var Version = "<unknown>"

// defaultPort is the port where cros-test will bind to in server mode if a port is not provided.
var defaultPort = 8001

// createLogFile creates a file and its parent directory for logging purpose.
func createLogFile(fullPath string) (*os.File, error) {
	if err := os.MkdirAll(fullPath, 0755); err != nil {
		return nil, errors.NewStatusError(errors.IOCreateError,
			fmt.Errorf("failed to create directory %v: %w", fullPath, err))
	}

	logFullPathName := filepath.Join(fullPath, "log.txt")

	// Log the full output of the command to disk.
	logFile, err := os.Create(logFullPathName)
	if err != nil {
		return nil, errors.NewStatusError(errors.IOCreateError,
			fmt.Errorf("failed to create file %v: %w", fullPath, err))
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
	logPath         string
	inputPath       string
	outputPath      string
	resultsDirPath  string
	tlwAddr         string
	metadataDirPath string
	version         bool

	// Server mode params
	port int
}

// runCLI is the entry point for running cros-test (executionservice) in CLI mode.
func runCLI(ctx context.Context, d []string) int {
	t := time.Now()
	defaultLogPath := filepath.Join(common.TestExecServerRoot, t.Format("20060102-150405"))
	defaultRequestFile := filepath.Join(common.TestExecServerRoot, common.TestRequestJSONFile)
	defaultResultFile := filepath.Join(common.TestExecServerRoot, common.TestResultJSONFile)

	a := args{}

	fs := flag.NewFlagSet("Run cros-test", flag.ExitOnError)
	fs.StringVar(&a.logPath, "log", defaultLogPath, fmt.Sprintf("Path to record execution logs. Default value is %s", defaultLogPath))
	fs.StringVar(&a.inputPath, "input", defaultRequestFile, "specify the test execution request json input file")
	fs.StringVar(&a.outputPath, "output", defaultResultFile, "specify the test execution response json output file")
	fs.StringVar(&a.resultsDirPath, "resultdir", common.TestResultDir, "specify default directory for test harnesses to store their run result")
	fs.StringVar(&a.tlwAddr, "tlwaddr", "", "specify the tlw address")
	fs.StringVar(&a.metadataDirPath, "metadatadir", common.TestMetadataDir, "specify a directory that contain all test metadata proto files.")
	fs.BoolVar(&a.version, "version", false, "print version and exit")
	fs.Parse(d)

	if a.version {
		fmt.Println("executionservice version ", Version)
		return 0
	}

	logFile, err := createLogFile(a.logPath)
	if err != nil {
		log.Fatalln("Failed to create log file", err)
		return 2
	}
	defer logFile.Close()

	logger := newLogger(logFile)
	logger.Println("Starting executionservice version ", Version)

	req, err := readInput(a.inputPath)
	if err != nil {
		log.Fatalf("Failed to read request input: %s", err)
		return 2
	}

	metadata, err := metadata.ReadDir(a.metadataDirPath)
	if err != nil {
		log.Fatalf("Failed to read metadata input: %s", err)
		return 2
	}

	rspn, err := runTests(ctx, logger, a.resultsDirPath, a.tlwAddr, metadata, req)
	if err != nil {
		logger.Fatalln("Failed to run tests: ", err)
		return 1
	}

	logger.Printf("Writing line to %s", a.outputPath)
	if err := writeOutput(a.outputPath, rspn); err != nil {
		logger.Fatalf("Failed to write output file to %s: %d", a.outputPath, err)
		return 2
	}
	return 0
}

// startServer is the entry point for running cros-test (executionservice) in server mode.
func startServer(d []string) int {
	a := args{}
	t := time.Now()
	defaultLogPath := filepath.Join(common.TestExecServerRoot, t.Format("20060102-150405"))

	fs := flag.NewFlagSet("Start executionservice server", flag.ExitOnError)
	fs.StringVar(&a.logPath, "log", defaultLogPath, fmt.Sprintf("Path to record execution logs. Default value is %s", defaultLogPath))
	fs.StringVar(&a.resultsDirPath, "resultdir", common.TestResultDir, "specify the test execution request json input file")
	fs.StringVar(&a.tlwAddr, "tlwaddr", "", "specify the tlw address")
	fs.StringVar(&a.metadataDirPath, "metadatadir", common.TestMetadataDir, "specify a directory that contain all test metadata proto files.")
	fs.IntVar(&a.port, "port", defaultPort, fmt.Sprintf("Specify the port for the server. Default value %d.", defaultPort))
	fs.Parse(d)

	logFile, err := createLogFile(a.logPath)
	if err != nil {
		log.Fatalln("Failed to create log file", err)
		return 2
	}
	defer logFile.Close()

	logger := newLogger(logFile)

	l, err := net.Listen("tcp", fmt.Sprintf(":%d", a.port))
	if err != nil {
		logger.Fatalln("Failed to create a net listener: ", err)
		return 2
	}
	logger.Println("Starting executionservice on port ", a.port)

	// Write port number to ~/.cftmeta for go/cft-port-discovery
	err = portdiscovery.WriteServiceMetadata("cros-test", l.Addr().String(), logger)
	if err != nil {
		logger.Println("Warning: error when writing to metadata file: ", err)
	}

	metadata, err := metadata.ReadDir(a.metadataDirPath)
	if err != nil {
		log.Fatalf("Failed to read metadata input: %s", err)
		return 2
	}

	server, closer := NewServer(logger, a.resultsDirPath, a.tlwAddr, metadata)
	defer closer()
	err = server.Serve(l)
	if err != nil {
		logger.Fatalln("Failed to initialize server: ", err)
		return 2
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

	runCliDefault runMode = "cliDefault"
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
		case "help":
			return runHelp, nil
		}
	}

	// If we did not find special run mode then just run CLI to match legacy behavior.
	return runCliDefault, nil
}

func mainInternal(ctx context.Context) int {
	runMode, err := getRunMode()
	if err != nil {
		log.Fatalln(err)
		return 2
	}
	switch runMode {

	case runCliDefault:
		log.Printf("No mode specified, assuming CLI.")
		return runCLI(ctx, os.Args)
	case runCli:
		log.Printf("Running CLI mode!")
		return runCLI(ctx, os.Args[2:])
	case runServer:
		log.Printf("Running server mode!")
		return startServer(os.Args[2:])
	case runVersion:
		log.Printf("executionservice version: %s", Version)
		return 0
	}
	return 0
}

func main() {
	os.Exit(mainInternal(context.Background()))
}
