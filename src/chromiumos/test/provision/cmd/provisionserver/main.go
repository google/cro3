// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the provisionservice used to setup CrOS devices
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

	"go.chromium.org/luci/common/errors"
)

// Version is the version info of this command. It is filled in during emerge.
var Version = "<0.1>"

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

type args struct {
	dutName string

	// Service required for provisioning.
	dutServiceAddr    string
	wiringServiceAddr string
	serverPort        int

	// Input and output json pb files.
	inputPath  string
	outputPath string
}

func (a *args) addCommonFlags(fs *flag.FlagSet) {
	fs.StringVar(&a.dutName, "dut-name", "", "the name of the DUT to be interfaced with.")

	fs.StringVar(&a.dutServiceAddr, "dut-service-address", "", "grcp address for dut-service.")
	fs.StringVar(&a.wiringServiceAddr, "wiring-service-address", "", "wiring address TLW.")
}

func (a *args) verifyCommon() error {
	if a.dutServiceAddr == "" {
		return errors.Reason("dut-service-address must be provided").Err()
	}
	// Necessary for now to move GCS data to DUT. Can be removed when another service is created.
	if a.wiringServiceAddr == "" {
		return errors.Reason("wiring-service-address must be provided").Err()
	}
	return nil
}

func (a *args) verifyServerInput(d []string) error {
	fs := flag.NewFlagSet("Provision", flag.ExitOnError)
	a.addCommonFlags(fs)
	fs.IntVar(&a.serverPort, "port", 0, "port used to start server.")
	fs.Parse(d)

	if err := a.verifyCommon(); err != nil {
		return err
	}
	if a.serverPort <= 0 {
		return errors.Reason("port to start server is not provided").Err()
	}
	return nil
}
func (a *args) verifyCLIInput(d []string) error {
	fs := flag.NewFlagSet("Provision", flag.ExitOnError)
	a.addCommonFlags(fs)
	fs.StringVar(&a.inputPath, "in-json", "", "path to json pb file to read input provision state.")
	fs.StringVar(&a.outputPath, "out-json", "", "path to json pb file to write output of provisioning.")
	fs.Parse(d)

	if err := a.verifyCommon(); err != nil {
		return err
	}
	if a.inputPath == "" {
		return errors.Reason("in-json must be provided").Err()
	}
	if a.outputPath == "" {
		return errors.Reason("out-json must be provided").Err()
	}
	return nil
}

func mainInternal(ctx context.Context) int {
	if len(os.Args) < 2 {
		log.Fatalln("please provide arguments")
		return 2
	}

	logFile, err := createLogFile()
	if err != nil {
		log.Fatalln("Failed to create log file: ", err)
		return 1
	}
	defer logFile.Close()
	logger := newLogger(logFile)
	logger.Println("Starting provisionservice version ", Version)

	a := &args{}
	switch os.Args[1] {
	case "cli":
		if err := a.verifyCLIInput(os.Args[2:]); err != nil {
			logger.Fatalln("Failed verify input: ", err)
			return 2
		}
		p, closer, err := newProvision(logger, a.dutName, a.dutServiceAddr, a.wiringServiceAddr)
		defer closer()
		if err != nil {
			logger.Fatalln("Failed to create provision: ", err)
			return 2
		}
		if err := p.runCLI(ctx, a.inputPath, a.outputPath); err != nil {
			logger.Fatalln("Failed to perform provision: ", err)
			return 1
		}
	case "server":
		if err := a.verifyServerInput(os.Args[2:]); err != nil {
			logger.Fatalln("Failed verify input: ", err)
			return 2
		}
		p, closer, err := newProvision(logger, a.dutName, a.dutServiceAddr, a.wiringServiceAddr)
		defer closer()
		if err != nil {
			logger.Fatalln("Failed to create provision: ", err)
			return 2
		}
		if err := p.startServer(a.serverPort); err != nil {
			logger.Fatalln("Failed to perform provision: ", err)
			return 1
		}
	case "version":
		logger.Printf("Provisionservice version: %s", Version)
		return 0
	default:
		logger.Fatalln("Expected 'cli' or 'server' as subcommands.")
		return 2
	}
	return 0
}

func main() {
	os.Exit(mainInternal(context.Background()))
}
