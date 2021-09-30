// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the cros-test-finder for finding tests based on tags.
package main

import (
	"flag"
	"fmt"
	"io"
	"log"
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

// Version is the version info of this command. It is filled in during emerge.
var Version = "<unknown>"

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
	if err := jsonpb.Unmarshal(f, &req); err != nil {
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
	testIds := []*api.TestCase_Id{}
	for _, md := range mdList {
		testIds = append(testIds, md.TestCase.Id)
	}
	return &api.TestSuite{
		Name: name,
		Spec: &api.TestSuite_TestCaseIds{
			TestCaseIds: &api.TestCaseIdList{TestCaseIds: testIds},
		},
	}
}

func main() {
	os.Exit(func() int {
		t := time.Now()
		defaultLogPath := filepath.Join(defaultRootPath, t.Format("20060102-150405"))
		defaultRequestFile := filepath.Join(defaultRootPath, defaultInputFileName)
		defaultResultFile := filepath.Join(defaultRootPath, defaultOutputFileName)
		version := flag.Bool("version", false, "print version and exit")
		log := flag.String("log", defaultLogPath, "specify the cros-test-finder log directory")
		input := flag.String("input", defaultRequestFile, "specify the cros-test-finder request json input file")
		output := flag.String("output", defaultResultFile, "specify the cros-test-finder response json output file")
		metadataDir := flag.String("metadatadir", defaultTestMetadataDir,
			"specify a directory that contain all test metadata proto files.")

		flag.Parse()

		if *version {
			fmt.Println("cros-test-finder version ", Version)
			return 0
		}

		logFile, err := createLogFile(*log)
		if err != nil {
			return errors.WriteError(os.Stderr, err)
		}
		defer logFile.Close()

		logger := newLogger(logFile)
		logger.Println("cros-test-finder version ", Version)

		logger.Println("Reading metadata from directory: ", *metadataDir)
		allTestMetadata, err := metadata.ReadDir(*metadataDir)
		if err != nil {
			logger.Println("Error: ", err)
			return errors.WriteError(os.Stderr, err)
		}

		logger.Println("Reading input file: ", *input)
		req, err := readInput(*input)
		if err != nil {
			logger.Println("Error: ", err)
			return errors.WriteError(os.Stderr, err)
		}

		suiteName := combineTestSuiteNames(req.TestSuites)

		selectedTestMetadata, err := finder.MatchedTestsForSuites(allTestMetadata.Values, req.TestSuites)
		if err != nil {
			logger.Println("Error: ", err)
			return errors.WriteError(os.Stderr, err)
		}

		resultTestSuite := metadataToTestSuite(suiteName, selectedTestMetadata)

		logger.Println("Writing output file: ", *output)
		rspn := &api.CrosTestFinderResponse{TestSuites: []*api.TestSuite{resultTestSuite}}
		if err := writeOutput(*output, rspn); err != nil {
			logger.Println("Error: ", err)
			return errors.WriteError(os.Stderr, err)
		}

		return 0
	}())
}
