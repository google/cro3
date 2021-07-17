// Copyright 2021 The Chromium OS Authors. All rights reserved.
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
	"os"
	"path/filepath"
	"time"

	"chromiumos/test/execution/cmd/testexecserver/internal/metadata"
	"chromiumos/test/execution/errors"
)

// Version is the version info of this command. It is filled in during emerge.
var Version = "<unknown>"

// createLogFile creates a file and its parent directory for logging purpose.
func createLogFile() (*os.File, error) {
	t := time.Now()
	fullPath := filepath.Join("/tmp/testexecserver/", t.Format("20060102-150405"))
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

func main() {
	os.Exit(func() int {
		version := flag.Bool("version", false, "print version and exit")
		input := flag.String("input", "input.json", "specify the test execution request json input file")
		output := flag.String("output", "output.json", "specify the test execution response json output file")
		tlwAddr := flag.String("tlwaddr", "", "specify the tlw address")
		metadataDir := flag.String("metadatadir", "/usrlocal/testmetadata/",
			"specify a directory that contain all test metadata proto files.")

		flag.Parse()

		if *version {
			fmt.Println("executionservice version ", Version)
			return 0
		}

		logFile, err := createLogFile()
		if err != nil {
			return errors.WriteError(os.Stderr, err)
		}
		defer logFile.Close()

		logger := newLogger(logFile)
		logger.Println("Starting executionservice version ", Version)

		req, err := readInput(*input)
		if err != nil {
			return errors.WriteError(os.Stderr, err)
		}

		metadata, err := metadata.ReadDir(*metadataDir)
		if err != nil {
			return errors.WriteError(os.Stderr, err)
		}
		ctx := context.Background()
		rspn, err := runTests(ctx, logger, *tlwAddr, metadata, req)
		if err != nil {
			return errors.WriteError(os.Stderr, err)
		}
		if err := writeOutput(*output, rspn); err != nil {
			return errors.WriteError(os.Stderr, err)
		}
		return 0
	}())
}
