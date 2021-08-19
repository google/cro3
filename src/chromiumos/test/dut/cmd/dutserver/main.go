// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the dutserver for interfacing with the DUT.

package main

import (
	"chromiumos/test/dut/cmd/dutserver/dutssh"
	"context"
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
	fullPath := filepath.Join("/tmp/dutserver/", t.Format("20060102-150405"))
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

		dutName := flag.String("dut_name", "", "DUT name to connect to. Mutually exclusive from dut_address. E.g.: chromeos1-row1-rack9-host4.")
		dutAddress := flag.String("dut_address", "", "DUT address to connect to. Mutually exclusive from dut_name. A DUT address must be in the format address:port. E.g.: 1.2.3.4:8080")
		wiringAddress := flag.String("wiring_address", "", "Address to TLW. Only required if using DUT name.")
		protoChunkSize := flag.Int64("chunk_size", 1024*1024, "Largest size of blob or coredumps to include in an individual response.")
		serializerPath := flag.String("serializer_path", "/usr/local/sbin/crash_serializer", "Location of the serializer binary on disk in the DUT.")
		port := flag.Int("port", 0, "the port used to start service. default not specified")
		flag.Parse()

		if os.Args[1] == "version" {
			fmt.Println("dutservice version ", Version)
			return 0
		}

		if *dutAddress == "" && *dutName == "" {
			fmt.Println("A DUT address or DUT name must be specified.")
		}

		if *dutName != "" && *dutAddress != "" {
			fmt.Println("DUT address and DUT name are mutually exclusive.")
		}

		if *dutName != "" && *wiringAddress == "" {
			fmt.Println("A Wiring address must be valid if DUT name is used.")
		}

		if *dutAddress != "" && *wiringAddress != "" {
			fmt.Println("A Wiring address should not be specified if DUT address is used.")
		}

		if *port == 0 {
			fmt.Println("Please specify the port.")
			return 2
		}

		logFile, err := createLogFile()
		if err != nil {
			log.Fatalln("Failed to create log file: ", err)
		}
		defer logFile.Close()

		logger := newLogger(logFile)
		logger.Println("Starting dutservice version ", Version)
		logger.Println("Starting dutservice on port ", *port)
		l, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
		if err != nil {
			logger.Fatalln("Failed to create a net listener: ", err)
			return 2
		}

		ctx := context.Background()
		conn, err := GetConnection(ctx, *dutName, *wiringAddress)
		if err != nil {
			logger.Fatalln("Failed to connect to dut: ", err)
			return 2
		}

		server, destructor := newDutServiceServer(l, logger, &dutssh.SSHClient{Client: conn}, *serializerPath, *protoChunkSize, *dutName, *wiringAddress)
		defer destructor()

		err = server.Serve(l)
		if err != nil {
			logger.Fatalln("Failed to initialize server: ", err)
		}
		return 0
	}())
}
