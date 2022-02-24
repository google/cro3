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
	"strings"
	"sync"

	"chromiumos/lro"

	"go.chromium.org/chromiumos/config/go/test/api"

	"chromiumos/test/execution/cmd/cros-test/internal/common"
	"chromiumos/test/execution/cmd/cros-test/internal/device"
	"chromiumos/test/execution/cmd/cros-test/internal/tautoresults"
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

// Name returns the name of the driver.
func (td *TautoDriver) Name() string {
	return "tauto"
}

// RunTests drives a test framework to execute tests.
func (td *TautoDriver) RunTests(ctx context.Context, resultsDir string, req *api.CrosTestRequest, tlwAddr string, tests []*api.TestCaseMetadata) (*api.CrosTestResponse, error) {
	primary := req.Primary
	companions := req.Companions
	testNamesToIds := getTestNamesToIds(tests)
	testNames := getTestNames(tests)

	addr, err := device.Address(primary)
	if err != nil {
		return nil, fmt.Errorf("cannot get address from DUT: %v", primary)
	}
	var companionAddrs []string
	for _, c := range companions {
		address, err := device.Address(c)
		if err != nil {
			return nil, fmt.Errorf("cannot get address from companion device: %v", c)
		}
		companionAddrs = append(companionAddrs, address)
	}

	// Fill in DUT server var flags.
	var dutServers []string
	if primary.DutServer != nil {
		dutServers = append(dutServers, fmt.Sprintf("%s:%d", primary.DutServer.Address, primary.DutServer.GetPort()))
	}
	for _, c := range companions {
		if c.DutServer != nil {
			dutServers = append(dutServers, fmt.Sprintf("%s:%d", c.DutServer.Address, c.DutServer.GetPort()))
		}
	}

	args := newTautoArgs(addr, companionAddrs, testNames, dutServers, resultsDir)

	// Run RTD.
	cmd := exec.Command("/usr/bin/test_that", genTautoArgList(args)...)
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

	results, err := tautoresults.TestsReports(resultsDir, testNames, testNamesToIds)

	if err != nil {
		return &api.CrosTestResponse{}, err
	}

	return &api.CrosTestResponse{TestCaseResults: results}, nil
}

// Flag names. More to be populated once impl details are firmed.
const (
	autotestDirFlag     = "--autotest_dir"
	tautoResultsDirFlag = "--results_dir"
	companionFlag       = "--companion_hosts"
	dutServerFlag       = "--dut_servers"
)

// tautoRunArgs stores arguments to invoke tauto
type tautoRunArgs struct {
	target   string            // The url for the target machine.
	patterns []string          // The names of test to be run.
	runFlags map[string]string // The flags for tauto run command.
}

// newTautoArgs created an argument structure for invoking tauto
func newTautoArgs(dut string, companions, tests, dutServers []string, resultsDir string) *tautoRunArgs {
	args := tautoRunArgs{
		target: dut,
		runFlags: map[string]string{
			autotestDirFlag: common.AutotestDir,
		},
	}
	if len(companions) > 0 {
		companionsAddresses := strings.Join(companions, ",")
		args.runFlags[companionFlag] = companionsAddresses
	}
	if len(dutServers) > 0 {
		dutServerAddresses := strings.Join(dutServers, ",")
		args.runFlags[dutServerFlag] = dutServerAddresses
	}

	args.patterns = tests // TO-DO Support Tags
	args.runFlags[tautoResultsDirFlag] = resultsDir
	return &args
}

// genTautoArgList generates argument list for invoking Tauto
func genTautoArgList(args *tautoRunArgs) (argList []string) {
	for flag, value := range args.runFlags {
		argList = append(argList, fmt.Sprintf("%v=%v", flag, value))
	}
	argList = append(argList, args.target)
	argList = append(argList, args.patterns...)
	return argList
}
