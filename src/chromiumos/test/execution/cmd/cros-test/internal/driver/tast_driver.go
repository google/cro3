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
func (td *TastDriver) RunTests(ctx context.Context, resultsDir string, req *api.CrosTestRequest, tlwAddr string, tests []*api.TestCaseMetadata) (*api.CrosTestResponse, error) {
	testNamesToIds := getTestNamesToIds(tests)
	testNames := getTestNames(tests)

	reportServer, err := tastrpc.NewReportsServer(0, testNames, testNamesToIds, resultsDir)
	if err != nil {
		return nil, errors.NewStatusError(errors.ServerStartingError,
			fmt.Errorf("failed to create tast report server: %v", err))
	}
	defer reportServer.Stop()

	primary, err := device.FillDUTInfo(req.Primary, "")
	if err != nil {
		return nil, errors.NewStatusError(errors.InvalidArgument,
			fmt.Errorf("cannot get address from primary device: %v", primary))
	}
	var companions []*device.DutInfo
	for i, c := range req.Companions {
		info, err := device.FillDUTInfo(c, fmt.Sprintf("cd%d", i+1))
		if err != nil {
			return nil, errors.NewStatusError(errors.InvalidArgument,
				fmt.Errorf("cannot get address from companion device: %v", c))
		}
		companions = append(companions, info)
	}
	args := newTastArgs(primary, companions, testNames, resultsDir, reportServer.Address())

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
	err = cmd.Wait()
	if err != nil {
		td.logger.Println("Failed to run tast: ", err)
		MissingTestErrMsg = fmt.Sprintf("Test did not run due to %s", err)
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

	return &api.CrosTestResponse{TestCaseResults: results}, err
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
	waitUntilReadyFlag         = "-waituntilready"
	timeOutFlag                = "-timeout"
	keyfileFlag                = "-keyfile"
	reportsServerFlag          = "-reports_server"
	companionDUTFlag           = "-companiondut"
	varFlag                    = "-var"
)

// runArgs stores arguments to invoke Tast
type runArgs struct {
	primary    *device.DutInfo   // The information of the primary machine.
	patterns   []string          // The names of test to be run.
	tastFlags  map[string]string // The flags for tast.
	runFlags   map[string]string // The flags for tast run command.
	companions []*device.DutInfo // The information of the companion DUTs to be used for testing.
}

// newTastArgs created an argument structure for invoking tast
func newTastArgs(primary *device.DutInfo, companionDuts []*device.DutInfo, tests []string, resultsDir, rsAddress string) *runArgs {
	return &runArgs{
		primary: primary,
		tastFlags: map[string]string{
			verboseFlag: "true",
			logTimeFlag: "false",
		},
		runFlags: map[string]string{
			sshRetriesFlag:             "2",
			downloadDataFlag:           "batch",
			buildFlag:                  "false",
			downloadPrivateBundlesFlag: "true",
			timeOutFlag:                "3000",
			resultsDirFlag:             resultsDir,
			reportsServerFlag:          rsAddress,
		},
		patterns:   tests, // TO-DO Support Tags
		companions: companionDuts,
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
	for _, c := range args.companions {
		// example: -companiondut=cd1:127.0.0.1:2222
		argList = append(argList, fmt.Sprintf("%v=%s:%s", companionDUTFlag, c.Role, c.Addr))
	}

	// Fill in the servo var flags.
	servoStrs := ""
	if args.primary.Servo != "" {
		// Fill in the old servo var flag for backward compatibility.
		// example -var=servo=labstation:9996/
		argList = append(argList, fmt.Sprintf("%v=servo=%s", varFlag, args.primary.Servo))
		// Fill in the servo var flag
		servoStrs = fmt.Sprintf(":%s", args.primary.Servo)
	}
	for _, c := range args.companions {
		if c.Servo != "" {
			servoStrs = fmt.Sprintf("%s,%s:%s", servoStrs, c.Role, c.Servo)
		}
	}
	if servoStrs != "" {
		// example: -var=servers.servo=:labstation:9995,cd1:labstation:9998
		argList = append(argList, fmt.Sprintf("%v=servers.servo=%s", varFlag, servoStrs))
	}

	// Fill in DUT server var flags.
	dutServerStrs := ""
	if args.primary.DutServer != "" {
		// Fill in the servo var flag
		dutServerStrs = fmt.Sprintf(":%s", args.primary.DutServer)
	}
	for _, c := range args.companions {
		if c.DutServer != "" {
			dutServerStrs = fmt.Sprintf("%s,%s:%s", dutServerStrs, c.Role, c.DutServer)
		}
	}
	if dutServerStrs != "" {
		// example: var=servers.dut=:d1:22,cd1:d2:22,cd3:d3:22
		argList = append(argList, fmt.Sprintf("%v=servers.dut=%s", varFlag, dutServerStrs))
	}

	// Fill in libs server var flag.
	libsServerStr := ""
	if args.primary.LibsServer != "" {
		libsServerStr = fmt.Sprintf(":%s", args.primary.LibsServer)
	}
	if libsServerStr != "" {
		// example: var=servers.libs=:d1:22
		argList = append(argList, fmt.Sprintf("%v=servers.libs=%s", varFlag, libsServerStr))
	}

	// Fill in Provision server var flags.
	provisionServerStrs := ""
	if args.primary.ProvisionServer != "" {
		// Fill in the servo var flag
		provisionServerStrs = fmt.Sprintf(":%s", args.primary.ProvisionServer)
	}
	for _, c := range args.companions {
		if c.ProvisionServer != "" {
			provisionServerStrs = fmt.Sprintf("%s,%s:%s", provisionServerStrs, c.Role, c.ProvisionServer)
		}
	}
	if provisionServerStrs != "" {
		// example: -var=servers.provision=primary:p1:22,cd1:p2:22,cd2:p2:22
		argList = append(argList, fmt.Sprintf("%v=servers.provision=%s", varFlag, provisionServerStrs))
	}

	argList = append(argList, args.primary.Addr)
	argList = append(argList, args.patterns...)
	return argList
}
