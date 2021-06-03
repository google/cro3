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

// TautoDriver runs Tauto and report its results.
type TautoDriver struct {
	// logger provides logging service.
	logger *log.Logger

	// Long running operation manager
	manager *lro.Manager

	// operation name
	op string
}

// NewTautoDriver creates a new driver to run tests.
func NewTautoDriver(logger *log.Logger, manager *lro.Manager, op string) *TautoDriver {
	return &TautoDriver{
		logger:  logger,
		manager: manager,
		op:      op,
	}
}

// RunTests drives a test framework to execute tests.
func (td *TautoDriver) RunTests(ctx context.Context, req *api.RunTestsRequest, resultsDir string) {
	path := "/usr/local/autotest/site_utils/test_that.py" // Default path of test_that.

	if resultsDir != "" {
		// Make sure the result directory exists.
		if err := os.MkdirAll(resultsDir, 0755); err != nil {
			td.manager.SetError(td.op, status.Newf(codes.FailedPrecondition, "failed to create result directory %v", resultsDir))
			return
		}
	}

	args := newTautoArgs(req, resultsDir)

	// Run RTD.
	cmd := exec.Command(path, genTautoArgList(args)...)
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
		td.manager.SetError(td.op, status.Newf(codes.FailedPrecondition, "failed to run Tauto: %v", err))
		return
	}
	var wg sync.WaitGroup
	wg.Add(2)

	go func() {
		defer wg.Done()
		scanner := bufio.NewScanner(stderr)
		for scanner.Scan() {
			td.logger.Printf("[tauto] %v", scanner.Text())
		}
	}()

	go func() {
		defer wg.Done()
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			td.logger.Printf("[tauto] %v", scanner.Text())
		}
	}()

	wg.Wait()

	if err := cmd.Wait(); err != nil {
		td.logger.Println("Failed to run tauto: ", err)
		td.manager.SetError(td.op, status.Newf(codes.Aborted, "fail to run tauto: %s", err))
		return
	}
	// TODO: set test response.
	td.manager.SetResult(td.op, &api.RunTestsResponse{})
	return
}

// Flag names. More to be populated once impl details are firmed.
const (
	autotest_dir         = "--autotest_dir"
	tauto_resultsDirFlag = "--results_dir"
)

// tautoRunArgs stores arguments to invoke tauto
type tautoRunArgs struct {
	target   string            // The url for the target machine.
	patterns []string          // The names of test to be run.
	runFlags map[string]string // The flags for tauto run command.
}

// newTautoArgs created an argument structure for invoking tauto
func newTautoArgs(req *api.RunTestsRequest, resultsDir string) *tautoRunArgs {
	args := tautoRunArgs{
		target: req.Dut.PrimaryHost,
		runFlags: map[string]string{
			autotest_dir: "/usr/local/autotest/",
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
		resultsDir = filepath.Join("/tmp/results/autotest", t.Format("20060102-150405"))
	}

	args.runFlags[tauto_resultsDirFlag] = resultsDir
	fmt.Println(args)
	return &args
}

// genArgList generates argument list for invoking Tauto
func genTautoArgList(args *tautoRunArgs) (argList []string) {
	for flag, value := range args.runFlags {
		argList = append(argList, fmt.Sprintf("%v=%v", flag, value))
	}
	argList = append(argList, args.target)
	argList = append(argList, args.patterns...)
	return argList
}
