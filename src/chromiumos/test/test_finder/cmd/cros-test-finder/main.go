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
	"time"

	"chromiumos/test/execution/errors"
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
		logger.Println("cros-test-finder input file: ", *input)
		logger.Println("cros-test-finder output file ", *output)
		logger.Println("cros-test-finder metadata directory: ", *metadataDir)

		return 0
	}())
}
