// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the provisionservice used to setup CrOS devices
package main

import (
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"path/filepath"
	"time"
)

// Version is the version info of this command. It is filled in during emerge.
var Version = "<unknown>"

// createLogFile creates a file and its parent directory for logging purpose.
func createLogFile() (*os.File, error) {
	t := time.Now()
	fullPath := filepath.Join("/tmp/provisionservice/", t.Format("20060102-150405"))
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
		version := flag.Bool("version", false, "print version and exit")
		flag.Parse()

		if *version {
			fmt.Println("provisionservice version ", Version)
			return 0
		}

		logFile, err := createLogFile()
		if err != nil {
			log.Fatalln("Failed to create log file: ", err)
		}
		defer logFile.Close()

		logger := newLogger(logFile)
		logger.Println("Starting provisionservice version ", Version)
		l, err := net.Listen("tcp", ":0")
		if err != nil {
			logger.Fatalln("Failed to create a net listener: ", err)
			return 2
		}
		server, err := newProvisionServer(l, logger)
		if err != nil {
			logger.Fatalln("Failed to start provisionservice server: ", err)
		}

		server.Serve(l)
		return 0
	}())
}
