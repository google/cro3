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
	"os/exec"
	"sync"

	"go.chromium.org/chromiumos/config/go/test/api"

	"chromiumos/test/execution/cmd/cros-test/internal/device"
	"chromiumos/test/execution/cmd/cros-test/internal/tastrpc"
	"chromiumos/test/execution/errors"
)

// TastDriver runs tast and report its results.
type TastDriver struct {
	// logger provides logging service.
	logger *log.Logger
}

// NewTastDriver creates a new driver to run tast tests.
func NewTastDriver(logger *log.Logger) *TastDriver {
	return &TastDriver{
		logger: logger,
	}
}

// Name returns the name of the driver.
func (td *TastDriver) Name() string {
	return "tast"
}

// RunTests drives a test framework to execute tests.
func (td *TastDriver) RunTests(ctx context.Context, resultsDir string, primary *api.CrosTestRequest_Device, tlwAddr string, tests []*api.TestCaseMetadata) (*api.CrosTestResponse, error) {
	testNamesToIds := getTestNamesToIds(tests)
	testNames := getTestNames(tests)

	reportServer, err := tastrpc.NewReportsServer(0, testNames, testNamesToIds, resultsDir)
	if err != nil {
		return nil, errors.NewStatusError(errors.ServerStartingError,
			fmt.Errorf("failed to create tast report server: %v", err))
	}
	defer reportServer.Stop()

	addr, err := device.Address(primary)
	if err != nil {
		return nil, errors.NewStatusError(errors.InvalidArgument,
			fmt.Errorf("cannot get address from primary device: %v", primary))
	}
	args := newTastArgs(addr, testNames, resultsDir, tlwAddr, reportServer.Address())

	// Run tast.
	cmd := exec.Command("/usr/bin/tast", genArgList(args)...)
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return nil, fmt.Errorf("failed to capture tast stderr: %v", err)
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		td.logger.Println("Failed to capture tast stdout: ", err)
		return nil, errors.NewStatusError(errors.IOCaptureError,
			fmt.Errorf("failed to capture tast stdout: %v", err))
	}
	td.logger.Println("Running Tast ", cmd.String())
	if err := cmd.Start(); err != nil {
		td.logger.Println("Failed to run tast: ", err)
		return nil, errors.NewStatusError(errors.CommandStartingError,
			fmt.Errorf("failed to run tast: %v", err))
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

	MissingTestErrMsg := ""
	if err := cmd.Wait(); err != nil {
		td.logger.Println("Failed to run tast: ", err)
		MissingTestErrMsg = fmt.Sprintf("Test did not run due to %s", err)
		return nil, errors.NewStatusError(errors.CommandExitError,
			fmt.Errorf("tast exited with error: %v", err))
	}

	testResults := reportServer.TestsReports()
	missingResults := reportServer.MissingTestsReports(MissingTestErrMsg)
	results := append(testResults, missingResults...)
	reportErrors := reportServer.Errors()
	if len(reportErrors) > 0 {
		for _, e := range reportErrors {
			td.logger.Printf("%v\n", e)
		}
		return &api.CrosTestResponse{TestCaseResults: results}, reportErrors[len(reportErrors)-1]
	}

	return &api.CrosTestResponse{TestCaseResults: results}, nil
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
func newTastArgs(dut string, tests []string, resultsDir, tlwAddress, rsAddress string) *runArgs {
	downloadPrivateBundles := "false"
	// Change downloadPrivateBundlesFlag to "true" if tlwServer is specified.
	if tlwAddress != "" {
		downloadPrivateBundles = "true"
	}
	return &runArgs{
		target: dut,
		tastFlags: map[string]string{
			verboseFlag: "true",
			logTimeFlag: "false",
		},
		runFlags: map[string]string{
			sshRetriesFlag:             "2",
			downloadDataFlag:           "batch",
			buildFlag:                  "false",
			downloadPrivateBundlesFlag: downloadPrivateBundles,
			timeOutFlag:                "3000",
			resultsDirFlag:             resultsDir,
			reportsServer:              rsAddress,
			tlwServerFlag:              tlwAddress,
		},
		patterns: tests, // TO-DO Support Tags
	}
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
