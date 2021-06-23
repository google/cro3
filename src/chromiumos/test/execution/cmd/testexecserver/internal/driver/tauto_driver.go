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

	"chromiumos/test/execution/cmd/testexecserver/internal/tautoresults"
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
func NewTautoDriver(logger *log.Logger) *TautoDriver {
	return &TautoDriver{
		logger: logger,
	}
}

// RunTests drives a test framework to execute tests.
func (td *TautoDriver) RunTests(ctx context.Context, resultsDir, dut, tlwAddr string, tests []string) (*api.RunTestsResponse, error) {
	path := "/usr/bin/test_that" // Default path of test_that.

	if resultsDir != "" {
		// Make sure the result directory exists.
		if err := os.MkdirAll(resultsDir, 0755); err != nil {
			return nil, fmt.Errorf("failed to create result directory %v", resultsDir)
		}
	}

	args := newTautoArgs(dut, tests, resultsDir)

	// Run RTD.
	cmd := exec.Command(path, genTautoArgList(args)...)
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return nil, fmt.Errorf("StderrPipe failed")
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, fmt.Errorf("StdoutPipe failed")
	}
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("failed to run Tauto: %v", err)
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
		return nil, fmt.Errorf("fail to run tauto: %s", err)
	}

	results, err := tautoresults.TestsReports(resultsDir, tests)

	if err != nil {
		return &api.RunTestsResponse{}, err
	}

	return &api.RunTestsResponse{TestCaseResults: results}, nil
}

// Flag names. More to be populated once impl details are firmed.
const (
	autotestDir         = "--autotest_dir"
	tautoResultsDirFlag = "--results_dir"
)

// tautoRunArgs stores arguments to invoke tauto
type tautoRunArgs struct {
	target   string            // The url for the target machine.
	patterns []string          // The names of test to be run.
	runFlags map[string]string // The flags for tauto run command.
}

// newTautoArgs created an argument structure for invoking tauto
func newTautoArgs(dut string, tests []string, resultsDir string) *tautoRunArgs {
	args := tautoRunArgs{
		target: dut,
		runFlags: map[string]string{
			autotestDir: "/usr/local/autotest/",
		},
	}

	args.patterns = tests // TO-DO Support Tags

	if resultsDir == "" {
		t := time.Now()
		resultsDir = filepath.Join("/tmp/results/autotest", t.Format("20060102-150405"))
	}

	args.runFlags[tautoResultsDirFlag] = resultsDir
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
