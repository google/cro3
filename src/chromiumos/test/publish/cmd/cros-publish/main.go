// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the cros-publish used to upload artifacts to GCS
// bucket.
package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"chromiumos/test/publish/cmd/publishserver"
	"go.chromium.org/luci/common/errors"
)

const (
	// version is the version info of this command. It is filled in during emerge.
	version         = "<unknown>"
	helpDescription = `cros-publish tool

The tool allows to upload test result artifacts to GCS buckets for testing
needs. Please read go/cros-upload-to-gs-tko-design-proposal for mode details.

Commands:
  cli       Running publish server in CLI mode result will be printed to output
						file.
            usage: cros-publish cli -service_account_creds service_account_file

  server    Starting server and allow work with server by RPC calls. Mostly
						used for tests.
            usage: cros-publish server -service_account_creds service_account_file [-port 80]

  -version  Print version of lib.
  -help     Print this help.`
	defaultLogDirectory = "/tmp/publish/"
	defaultPort         = 80
)

// createLogFile creates a file and its parent directory for logging purpose.
func createLogFile() (*os.File, error) {
	t := time.Now()
	fullPath := filepath.Join(defaultLogDirectory, t.Format("20060102-150405"))
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
	// Common input params.
	// Local directory that will be uploaded.
	localDir string
	// GCS bucket path where the local directory will be uploaded to.
	gsDir string
	// Service account file containing gcp credentials.
	serviceAccountCreds string
	// Output log file.
	outputPath string

	// Server mode params
	port int
}

func validate(a args) error {
	if a.serviceAccountCreds == "" {
		return errors.Reason("Service account file not specified").Err()
	}

	_, err := os.Open(a.serviceAccountCreds)
	if err != nil {
		return errors.Reason("Failed to read service account file").Err()
	}
	return nil
}

func runCLI(ctx context.Context, d []string) int {
	a := args{}
	fs := flag.NewFlagSet("Start publish publishService", flag.ExitOnError)
	fs.StringVar(&a.localDir, "local_dir", "", "path to the local directory that will be uploaded")
	fs.StringVar(&a.gsDir, "gs_dir", "", "path to the GCS bucket where the local directory will be uploaded to")
	fs.StringVar(&a.serviceAccountCreds, "service_account_creds", "", "path to service account file containing gcp credentials")
	fs.StringVar(&a.outputPath, "output", "", "path to the response jsonproto output file.")
	fs.Parse(d)

	logFile, err := createLogFile()
	if err != nil {
		log.Fatalln("Failed to create log file", err)
		return 2
	}
	defer logFile.Close()

	logger := newLogger(logFile)
	if err := validate(a); err != nil {
		log.Fatalf("Validate arguments fail: %s", err)
		return 2
	}

	publishService, destructor, err := publishserver.NewPublishService(ctx, a.serviceAccountCreds, logger)
	defer destructor()
	if err != nil {
		logger.Fatalln("Failed to create publish: ", err)
		return 2
	}

	if err := publishService.RunCli(ctx, a.localDir, a.gsDir, a.outputPath); err != nil {
		logger.Fatalln("Failed to perform publish: ", err)
		return 1
	}
	return 0
}

func startServer(ctx context.Context, d []string) int {
	a := args{}
	fs := flag.NewFlagSet("Start publish publishService", flag.ExitOnError)
	fs.StringVar(&a.serviceAccountCreds, "service_account_creds", "", "path to service account file containing gcp credentials")
	fs.IntVar(&a.port, "port", defaultPort, fmt.Sprintf("Specify the port for the publishService. Default value %d.", defaultPort))
	fs.Parse(d)

	logFile, err := createLogFile()
	if err != nil {
		log.Fatalln("Failed to create log file", err)
		return 2
	}
	defer logFile.Close()

	logger := newLogger(logFile)
	if err := validate(a) ; err != nil {
		log.Fatalf("Validate arguments fail: %s", err)
		return 2
	}

	publishService, destructor, err := publishserver.NewPublishService(ctx, a.serviceAccountCreds, logger)
	defer destructor()
	if err != nil {
		logger.Fatalln("Failed to create publish: ", err)
		return 2
	}

	if err := publishService.StartServer(a.port); err != nil {
		logger.Fatalln("Failed to perform publish: ", err)
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

func mainInternal() int {
	rm, err := getRunMode()
	if err != nil {
		log.Fatalln(err)
		return 2
	}

	ctx := context.Background()
	switch rm {
	case runCli:
		log.Printf("Running CLI mode!")
		return runCLI(ctx, os.Args[2:])
	case runServer:
		log.Printf("Running server mode!")
		return startServer(ctx, os.Args[2:])
	case runVersion:
		log.Printf("cros-publish version: %s", version)
		return 0
	}

	log.Printf(helpDescription)
	return 0
}

func main() {
	os.Exit(mainInternal())
}
