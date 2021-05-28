// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package driver implements drivers to execute tests.
package driver

import (
	"bufio"
	"context"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"time"

	"chromiumos/lro"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// TastDriver runs tast and report its results.
type TastDriver struct {
	// logger provides logging service.
	logger *log.Logger

	// Long running operation manager
	manager *lro.Manager

	// operation name
	op string
}

// NewTastDriver creates a new driver to run tast tests.
func NewTastDriver(logger *log.Logger, manager *lro.Manager, op string) *TastDriver {
	return &TastDriver{
		logger:  logger,
		manager: manager,
		op:      op,
	}
}

// RunTests drives a test framework to execute tests.
func (td *TastDriver) RunTests(ctx context.Context, req *api.RunTestsRequest, resultsDir string) {
	path := "/usr/bin/tast" // Default path of tast which can be overridden later.

	if resultsDir != "" {
		// Make sure the result directory exists.
		if err := os.MkdirAll(resultsDir, 0755); err != nil {
			td.manager.SetError(td.op, status.Newf(codes.FailedPrecondition, "failed to create result directory %v", resultsDir))
			return
		}
	}

	args := newTastArgs(req, resultsDir)

	// Run tast.
	cmd := exec.Command(path, genArgList(args)...)
	stderr, err := cmd.StderrPipe()
	if err != nil {
		td.manager.SetError(td.op, status.New(codes.FailedPrecondition, "StderrPipe failed"))
		return
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		td.manager.SetError(td.op, status.New(codes.FailedPrecondition, "StdoutPipe failed"))
		return
	}
	if err := cmd.Start(); err != nil {
		td.manager.SetError(td.op, status.Newf(codes.FailedPrecondition, "failed to run tast: %v", err))
		return
	}
	var wg sync.WaitGroup
	wg.Add(2)

	go func() {
		defer wg.Done()
		scanner := bufio.NewScanner(stderr)
		for scanner.Scan() {
			td.logger.Printf("[tast] %v", scanner.Text())
		}
	}()

	go func() {
		defer wg.Done()
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			td.logger.Printf("[tast] %v", scanner.Text())
		}
	}()

	wg.Wait()

	if err := cmd.Wait(); err != nil {
		td.logger.Println("Failed to run tast: ", err)
		td.manager.SetError(td.op, status.Newf(codes.Aborted, "fail to run tast: %s", err))
		return
	}
	// TODO: set test response.
	td.manager.SetResult(td.op, &api.RunTestsResponse{})
	return
}

// Command name and flag names.
const (
	runSubcommand              = "run"
	verboseFlag                = "-verbose"
	logTimeFlag                = "-logtime"
	sshRetriesFlag             = "-sshretries"
	downloadDataFlag           = "-downloaddata"
	buildFlag                  = "-build"
	remoteBundlerDirFlag       = "-remotebundledir"
	remoteDataDirFlag          = "-remotedatadir"
	remoteRunnerFlag           = "-remoterunner"
	defaultVarsDirFlag         = "-defaultvarsdir"
	downloadPrivateBundlesFlag = "-downloadprivatebundles"
	devServerFlag              = "-devservers"
	resultsDirFlag             = "-resultsdir"
	tlwServerFlag              = "-tlwserver"
	waitUntilReadyFlag         = "-waituntilready"
	timeOutFlag                = "-timeout"
	keyfile                    = "-keyfile"
	reportsServer              = "-reports_server"
)

// runArgs stores arguments to invoke Tast
type runArgs struct {
	target    string            // The url for the target machine.
	patterns  []string          // The names of test to be run.
	tastFlags map[string]string // The flags for tast.
	runFlags  map[string]string // The flags for tast run command.
}

// newTastArgs created an argument structure for invoking tast
func newTastArgs(req *api.RunTestsRequest, resultsDir string) *runArgs {
	args := runArgs{
		target: req.Dut.PrimaryHost,
		tastFlags: map[string]string{
			verboseFlag: "true",
			logTimeFlag: "false",
		},
		runFlags: map[string]string{
			sshRetriesFlag:             "2",
			downloadDataFlag:           "batch",
			buildFlag:                  "false",
			downloadPrivateBundlesFlag: "false", // Default to "false".
			timeOutFlag:                "3000",
		},
	}

	for _, suite := range req.TestSuites {
		for _, tc := range suite.TestCaseIds.TestCaseIds {
			args.patterns = append(args.patterns, tc.Value)
		}
		// TO-DO Support Tags
	}

	if resultsDir == "" {
		t := time.Now()
		resultsDir = filepath.Join("/tmp/tast/results", t.Format("20060102-150405"))
	}
	args.runFlags[resultsDirFlag] = resultsDir

	return &args
}

// genArgList generates argument list for invoking tast
func genArgList(args *runArgs) (argList []string) {
	for flag, value := range args.tastFlags {
		argList = append(argList, fmt.Sprintf("%v=%v", flag, value))
	}
	argList = append(argList, runSubcommand)
	for flag, value := range args.runFlags {
		argList = append(argList, fmt.Sprintf("%v=%v", flag, value))
	}
	argList = append(argList, args.target)
	argList = append(argList, args.patterns...)
	return argList
}
