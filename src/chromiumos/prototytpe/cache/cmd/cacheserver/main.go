// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"time"
)

// createLogFile creates a file and its parent directory for logging purpose.
func createLogFile() (*os.File, error) {
	t := time.Now()
	fullPath := filepath.Join("/tmp/cacheserver/", t.Format("20060102-150405"))
	if err := os.MkdirAll(fullPath, 0755); err != nil {
		return nil, fmt.Errorf("failed to create directory %v: %v", fullPath, err)
	}

	logFullPathName := filepath.Join(fullPath, "log.txt")

	// Log the full output of the command to disk.
	logFile, err := os.Create(logFullPathName)
	if err != nil {
		return nil, fmt.Errorf("failed to create file %v: %v", fullPath, err)
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
		flag.NewFlagSet("version", flag.ExitOnError)

		port := flag.Int("port", 8080, "Port Caching Server will listen to.")
		cacheLocation := flag.String("location", "/tmp/cacheserver", "Path to cache.")
		flag.Parse()

		logFile, err := createLogFile()
		if err != nil {
			log.Fatalln("Failed to create log file: ", err)
		}
		defer logFile.Close()

		logger := newLogger(logFile)
		logger.Println("Starting cacheservice")

		if err := InstantiateHandlers(*port, *cacheLocation); err != nil {
			log.Fatalln("failed to instantiate http handlers: ", err)
		}

		return 0
	}())
}
