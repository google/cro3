// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the cros-test-finder for finding tests based on tags.
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

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/chromiumos/config/go/test/api"

	"chromiumos/test/execution/errors"
	"chromiumos/test/util/finder"
	"chromiumos/test/util/metadata"
)

const (
	defaultRootPath        = "/tmp/test/cros-test-finder"
	defaultInputFileName   = "request.json"
	defaultOutputFileName  = "result.json"
	defaultTestMetadataDir = "/tmp/test/metadata"
)

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

// readInput reads a CrosTestFinderRequest jsonproto file and returns a pointer to RunTestsRequest.
func readInput(fileName string) (*api.CrosTestFinderRequest, error) {
	f, err := os.Open(fileName)
	if err != nil {
		return nil, errors.NewStatusError(errors.IOAccessError,
			fmt.Errorf("fail to read file %v: %v", fileName, err))
	}
	req := api.CrosTestFinderRequest{}
	umrsh := jsonpb.Unmarshaler{}
	umrsh.AllowUnknownFields = true
	if err := umrsh.Unmarshal(f, &req); err != nil {
		return nil, errors.NewStatusError(errors.UnmarshalError,
			fmt.Errorf("fail to unmarshal file %v: %v", fileName, err))
	}
	return &req, nil
}

// writeOutput writes a CrosTestFinderResponse json.
func writeOutput(output string, resp *api.CrosTestFinderResponse) error {
	f, err := os.Create(output)
	if err != nil {
		return errors.NewStatusError(errors.IOCreateError,
			fmt.Errorf("fail to create file %v: %v", output, err))
	}
	m := jsonpb.Marshaler{}
	if err := m.Marshal(f, resp); err != nil {
		return errors.NewStatusError(errors.MarshalError,
			fmt.Errorf("failed to marshall response to file %v: %v", output, err))
	}
	return nil
}

// combineTestSuiteNames combines a list of test suite names to one single name.
func combineTestSuiteNames(suites []*api.TestSuite) string {
	if len(suites) == 0 {
		return "CombinedSuite"
	}
	var names []string
	for _, s := range suites {
		names = append(names, s.Name)
	}
	return strings.Join(names, ",")
}

// metadataToTestSuite convert a list of test metadata to a test suite.
func metadataToTestSuite(name string, mdList []*api.TestCaseMetadata) *api.TestSuite {
	testInfos := []*api.TestCase{}
	for _, md := range mdList {
		testInfos = append(testInfos, &api.TestCase{
			Id:           md.TestCase.Id,
			Dependencies: md.TestCase.Dependencies,
		})
	}
	return &api.TestSuite{
		Name: name,
		Spec: &api.TestSuite_TestCases{
			TestCases: &api.TestCaseList{TestCases: testInfos},
		},
	}
}

// Version is the version info of this command. It is filled in during emerge.
var Version = "<unknown>"
var defaultPort = 8010

type args struct {
	// Common input params.
	logPath     string
	inputPath   string
	output      string
	metadataDir string
	version     bool

	// Server mode params
	port int
}

func innerMain(logger *log.Logger, req *api.CrosTestFinderRequest, metadataDir string) (*api.CrosTestFinderResponse, error) {
	logger.Println("Reading metadata from directory: ", metadataDir)
	allTestMetadata, err := metadata.ReadDir(metadataDir)
	if err != nil {
		logger.Println("Error: ", err)
		return nil, errors.NewStatusError(errors.IOCreateError,
			fmt.Errorf("failed to read directory %v: %w", metadataDir, err))
	}

	suiteName := combineTestSuiteNames(req.TestSuites)

	selectedTestMetadata, err := finder.MatchedTestsForSuites(allTestMetadata.Values, req.TestSuites)
	if err != nil {
		logger.Println("Error: ", err)
		return nil, err
	}

	resultTestSuite := metadataToTestSuite(suiteName, selectedTestMetadata)

	rspn := &api.CrosTestFinderResponse{TestSuites: []*api.TestSuite{resultTestSuite}}
	return rspn, nil

}

// runCLI is the entry point for running cros-test (TestFinderService) in CLI mode.
func runCLI(ctx context.Context, d []string) int {
	t := time.Now()
	defaultLogPath := filepath.Join(defaultRootPath, t.Format("20060102-150405"))
	defaultRequestFile := filepath.Join(defaultRootPath, defaultInputFileName)
	defaultResultFile := filepath.Join(defaultRootPath, defaultOutputFileName)

	a := args{}

	fs := flag.NewFlagSet("Run cros-test", flag.ExitOnError)
	fs.StringVar(&a.logPath, "log", defaultLogPath, fmt.Sprintf("Path to record finder logs. Default value is %s", defaultLogPath))
	fs.StringVar(&a.inputPath, "input", defaultRequestFile, "specify the test finder request json input file")
	fs.StringVar(&a.output, "output", defaultResultFile, "specify the test finder request json input file")
	fs.StringVar(&a.metadataDir, "metadatadir", defaultTestMetadataDir, "specify a directory that contain all test metadata proto files.")
	fs.BoolVar(&a.version, "version", false, "print version and exit")
	fs.Parse(d)

	if a.version {
		fmt.Println("cros-test-finder version ", Version)
		return 0
	}

	logFile, err := createLogFile(a.logPath)
	if err != nil {
		log.Fatalln("Failed to create log file", err)
		return 2
	}
	defer logFile.Close()

	logger := newLogger(logFile)
	logger.Println("cros-test-finder version ", Version)

	logger.Println("Reading input file: ", a.inputPath)
	req, err := readInput(a.inputPath)
	if err != nil {
		logger.Println("Error: ", err)
		return errors.WriteError(os.Stderr, err)
	}

	rspn, err := innerMain(logger, req, a.metadataDir)
	if err != nil {
		return 2
	}

	logger.Println("Writing output file: ", a.output)
	if err := writeOutput(a.output, rspn); err != nil {
		logger.Println("Error: ", err)
		return errors.WriteError(os.Stderr, err)
	}

	return 0
}

// startServer is the entry point for running cros-test-finder (TestFinderService) in server mode.
func startServer(d []string) int {
	a := args{}
	t := time.Now()
	defaultLogPath := filepath.Join(defaultRootPath, t.Format("20060102-150405"))
	fs := flag.NewFlagSet("Run cros-test", flag.ExitOnError)
	fs.StringVar(&a.logPath, "log", defaultLogPath, fmt.Sprintf("Path to record finder logs. Default value is %s", defaultLogPath))
	fs.StringVar(&a.metadataDir, "metadatadir", defaultTestMetadataDir, "specify a directory that contain all test metadata proto files.")
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
	logger.Println("Starting TestFinderService on port ", a.port)

	server, closer := NewServer(logger, a.metadataDir)
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
		log.Printf("TestFinderService version: %s", Version)
		return 0
	}
	return 0
}

func main() {
	os.Exit(mainInternal(context.Background()))
}
