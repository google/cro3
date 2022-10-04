// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package driver implements drivers to execute tests.
package driver

import (
	"bufio"
	"context"
	"encoding/json"
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
	"chromiumos/test/execution/errors"
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
	testNamesToIds := getTestNamesToIds(tests)
	testNames := getTestNames(tests)

	primary, err := device.FillDUTInfo(req.Primary, "")
	var companions []*device.DutInfo
	for i, c := range req.Companions {
		info, err := device.FillDUTInfo(c, fmt.Sprintf("cd%d", i+1))
		if err != nil {
			return nil, errors.NewStatusError(errors.InvalidArgument,
				fmt.Errorf("cannot get address from companion device: %v", c))
		}
		companions = append(companions, info)
	}

	// Fill in DUT server var flags.
	var dutServers []string
	if primary.DutServer != "" {
		dutServers = append(dutServers, fmt.Sprintf("%s", primary.DutServer))
	}
	for _, c := range companions {
		if c.DutServer != "" {
			dutServers = append(dutServers, fmt.Sprintf("%s", c.DutServer))
		}
	}

	// Fill in DUT server var flags.
	var libsServer string
	if primary.LibsServer != "" {
		libsServer = fmt.Sprintf("%s", primary.LibsServer)
	}

	args, err := newTautoArgs(primary, companions, testNames, dutServers, resultsDir, libsServer)
	if err != nil {
		return nil, fmt.Errorf("failed to create tauto args: %v", err)
	}

	// Run RTD.
	cmd := exec.Command("/usr/bin/test_that", genTautoArgList(args)...)

	td.logger.Println("Running Autotest: ", cmd.String())

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

	const maxCapacity = 4096 * 1024

	go func() {
		defer wg.Done()
		scanner := bufio.NewScanner(stderr)
		// Expand the buffer size to avoid deadlocks on heavy logs
		buf := make([]byte, maxCapacity)
		scanner.Buffer(buf, maxCapacity)
		for scanner.Scan() {
			td.logger.Printf("[tauto] %v", scanner.Text())
		}
		if scanner.Err() != nil {
			td.logger.Println("Failed to read stdout Pipe: ", scanner.Err())
		}
	}()

	go func() {
		defer wg.Done()
		scanner := bufio.NewScanner(stdout)
		// Expand the buffer size to avoid deadlocks on heavy logs
		buf := make([]byte, maxCapacity)
		scanner.Buffer(buf, maxCapacity)
		for scanner.Scan() {
			td.logger.Printf("[tauto] %v", scanner.Text())
		}
		if scanner.Err() != nil {
			td.logger.Println("Failed to read stdout Pipe: ", scanner.Err())
		}
	}()

	wg.Wait()

	MissingTestErrMsg := ""
	if err := cmd.Wait(); err != nil {
		td.logger.Println("Failed to run Tauto: ", err)
		MissingTestErrMsg = fmt.Sprintf("Test did not run due to %s", err)
	}

	results, err := tautoresults.TestsReports(resultsDir, testNames, testNamesToIds, MissingTestErrMsg)

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
	libsServerFlag      = "--libs_server"
	// Must be formatted to test_that as follows: ... --host_labels label1 label2 label3
	// Thus, no quotes, etc just a space deliminated list of strings
	labels = "--host_labels"
	// Must be formatted to test_that as follows: ... --host_attributes='{"key": "value"}'
	// Thus, single quoted, with k/v in double quotes.
	attributes = "--host_attributes"
	// Setting the CFT has minor changes in Autotest, such as no exit(1) on failure.
	cft       = "--CFT"
	tautoArgs = "--args"
)

// tautoRunArgs stores arguments to invoke tauto
// Change target from string to the dut api
type tautoRunArgs struct {
	target   *device.DutInfo   // The information of the target machine.
	patterns []string          // The names of test to be run.
	runFlags map[string]string // The flags for tauto run command.
	cftFlag  string
}

// newTautoArgs created an argument structure for invoking tauto
func newTautoArgs(dut *device.DutInfo, companionDuts []*device.DutInfo, tests, dutServers []string, resultsDir string, libsServer string) (*tautoRunArgs, error) {
	args := tautoRunArgs{
		target: dut,
		runFlags: map[string]string{
			autotestDirFlag: common.AutotestDir,
		},
	}

	if len(companionDuts) > 0 {
		var companionsAddresses []string
		for _, c := range companionDuts {
			companionsAddresses = append(companionsAddresses, c.Addr)
		}
		args.runFlags[companionFlag] = strings.Join(companionsAddresses, ",")
	}

	tautoArgsStr := ""
	if len(dutServers) > 0 {
		dutServerAddresses := strings.Join(dutServers, ",")
		args.runFlags[dutServerFlag] = dutServerAddresses
		tautoArgsStr = tautoArgsStr + fmt.Sprintf("%v=%v", "dut_servers", dutServerAddresses)
	}

	if libsServer != "" {
		args.runFlags[libsServerFlag] = libsServer
		tautoArgsStr = tautoArgsStr + fmt.Sprintf(" %v=%v", "libs_server", libsServer)
	}

	args.runFlags[tautoArgs] = tautoArgsStr

	// Now we need to get a list of all labels, then load the labels const.
	attrMap, infoLabels, err := convertDutTopologyToHostInfo(dut)
	if err != nil {
		return nil, fmt.Errorf("failed to convert dutotopology: %v", err)
	}

	if len(infoLabels) > 0 {
		args.runFlags[labels] = strings.Join(infoLabels, " ")
	}

	if len(attrMap) > 0 {
		jsonStr, err := json.Marshal(attrMap)
		if err != nil {
			return nil, fmt.Errorf("failed to convert attrMap to string %v", err)
		}
		args.runFlags[attributes] = fmt.Sprintf("%v", string(jsonStr))
	}

	args.cftFlag = cft
	args.patterns = tests // TO-DO Support Tags
	args.runFlags[tautoResultsDirFlag] = resultsDir
	return &args, nil
}

func convertDutTopologyToHostInfo(dut *device.DutInfo) (map[string]string, []string, error) {
	attrMap, labels, err := appendChromeOsLabels(dut)
	if err != nil {
		return nil, nil, fmt.Errorf("Topology failed: %v", err)
	}
	return attrMap, labels, nil
}

// appendChromeOsLabels appends labels extracted from ChromeOS device.
func appendChromeOsLabels(dut *device.DutInfo) (map[string]string, []string, error) {
	// attrMap is the map of attributes to be used for autotest hostinfo.
	// example: {"servo_host": "servohostname.cros"}
	attrMap := make(map[string]string)

	// labels is a list of labels describing the DUT to be used for autotest hostinfo.
	// example: "servo chameleon audio_board"
	var labels []string

	if dut.Board != "" {
		labels = append(labels, "board:"+strings.ToLower(dut.Board))
	}
	if dut.Model != "" {
		labels = append(labels, "model:"+strings.ToLower(dut.Model))
	}

	// - Servo
	if dut.Servo != "" {
		labels = append(labels, "servo")
	}
	if dut.ServoHostname != "" {
		attrMap["servo_host"] = dut.ServoHostname
	}
	if dut.ServoPort != "" {
		attrMap["servo_port"] = dut.ServoPort
	}
	if dut.ServoSerial != "" {
		attrMap["servo_serial"] = dut.ServoSerial
	}

	if dut.ChamelonPresent == true {
		labels = append(labels, "chameleon")
	}
	if dut.ChameleonAudio == true {
		labels = append(labels, "audio_board")
	}
	if len(dut.ChamelonPeriphsList) > 0 {
		labels = append(labels, dut.ChamelonPeriphsList...)
	}

	if dut.AtrusAudio == true {
		labels = append(labels, "atrus")
	}

	if dut.TouchMimo == true {
		labels = append(labels, "mimo")
	}

	// - Camerabox
	if dut.CameraboxFacing != "" {
		labels = append(labels, "camerabox_facing:"+dut.CameraboxFacing)
	}

	if len(dut.CableList) > 0 {
		labels = append(labels, dut.CableList...)
	}

	return attrMap, labels, nil
}

// genTautoArgList generates argument list for invoking Tauto
func genTautoArgList(args *tautoRunArgs) (argList []string) {
	for flag, value := range args.runFlags {
		argList = append(argList, fmt.Sprintf("%v=%v", flag, value))
	}
	argList = append(argList, args.cftFlag)
	argList = append(argList, args.target.Addr)
	argList = append(argList, args.patterns...)
	return argList
}
