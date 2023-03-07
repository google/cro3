// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package driver

import (
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"sort"
	"strings"
	"testing"

	"github.com/google/go-cmp/cmp"
	"github.com/google/go-cmp/cmp/cmpopts"
	"gopkg.in/yaml.v2"

	"chromiumos/test/execution/cmd/cros-test/internal/device"
)

// TestNewTastArgs makes sure newTastArgs creates the correct arguments for tast.
func TestNewTastArgs(t *testing.T) {
	primary := &device.DutInfo{Addr: dut1, Role: ""}
	expectedArgs := runArgs{
		primary:  primary,
		patterns: []string{test1, test2, test3, test4, test5},
		tastFlags: map[string]string{
			verboseFlag: "true",
			logTimeFlag: "false",
		},
		runFlags: map[string]string{
			sshRetriesFlag:             "2",
			testRetriesFlag:            "2",
			downloadDataFlag:           "batch",
			buildFlag:                  "false",
			downloadPrivateBundlesFlag: "true",
			resultsDirFlag:             workDir1,
			reportsServerFlag:          ":5555",
			varsFile:                   "/tmp/test.yaml",
		},
	}

	args := newTastArgs(
		primary, nil, expectedArgs.patterns,
		workDir1, expectedArgs.runFlags[reportsServerFlag],
		expectedArgs.runFlags[varsFile],
	)
	if diff := cmp.Diff(args, &expectedArgs, cmp.AllowUnexported(runArgs{}), cmpopts.EquateEmpty()); diff != "" {
		t.Errorf("Got unexpected argument from newTastArgs (-got +want):\n%s\n%v\n--\n%v\n", diff, args, expectedArgs)
	}
}

// TestNewTastArgsCompanions makes sure newTastArgs creates the correct arguments for tast with companion DUTs.
func TestNewTastArgsCompanions(t *testing.T) {
	primary := &device.DutInfo{Addr: dut1, Role: ""}
	companions := []*device.DutInfo{
		{
			Addr: "companion_dut1_address",
			Role: "cd1",
		},
		{
			Addr: "companion_dut2_address",
			Role: "cd2",
		},
	}
	expectedArgs := runArgs{
		primary:  primary,
		patterns: []string{test1, test2, test3, test4, test5},
		tastFlags: map[string]string{
			verboseFlag: "true",
			logTimeFlag: "false",
		},
		runFlags: map[string]string{
			sshRetriesFlag:             "2",
			testRetriesFlag:            "2",
			downloadDataFlag:           "batch",
			buildFlag:                  "false",
			downloadPrivateBundlesFlag: "true",
			resultsDirFlag:             workDir1,
			reportsServerFlag:          ":5555",
			varsFile:                   "/tmp/test.yaml",
		},
		companions: companions,
	}

	args := newTastArgs(
		primary, companions, expectedArgs.patterns, workDir1,
		expectedArgs.runFlags[reportsServerFlag], expectedArgs.runFlags[varsFile])
	if diff := cmp.Diff(args, &expectedArgs, cmp.AllowUnexported(runArgs{})); diff != "" {
		t.Errorf("Got unexpected argument from newTastArgs (-got +want):\n%s", diff)
	}
}

// TestGenArgList makes sure genArgList generates the correct list of argument for tast.
func TestGenArgList(t *testing.T) {
	primary := &device.DutInfo{Addr: dut1, Role: ""}
	companions := []*device.DutInfo{
		{
			Addr: "companion_dut1_address",
			Role: "cd1",
		},
		{
			Addr: "companion_dut2_address",
			Role: "cd2",
		},
	}
	args := runArgs{
		primary:  primary,
		patterns: []string{test1, test2},
		tastFlags: map[string]string{
			verboseFlag: "true",
			logTimeFlag: "false",
		},
		runFlags: map[string]string{
			sshRetriesFlag:             "2",
			testRetriesFlag:            "2",
			downloadDataFlag:           "batch",
			buildFlag:                  "false",
			downloadPrivateBundlesFlag: "true",
			resultsDirFlag:             workDir1,
			reportsServerFlag:          "127.0.0.1:3333",
			varsFile:                   "/a/file",
		},
		companions: companions,
	}

	var expectedArgList []string
	for key, value := range args.tastFlags {
		expectedArgList = append(expectedArgList, fmt.Sprintf("%v=%v", key, value))
	}
	runIndex := len(expectedArgList)
	expectedArgList = append(expectedArgList, "run")
	for key, value := range args.runFlags {
		expectedArgList = append(expectedArgList, fmt.Sprintf("%v=%v", key, value))
	}
	for i, c := range companions {
		expectedArgList = append(expectedArgList, fmt.Sprintf("%v=cd%v:%v", companionDUTFlag, i+1, c.Addr))
	}
	dutIndex := len(expectedArgList)
	expectedArgList = append(expectedArgList, dut1)
	expectedArgList = append(expectedArgList, test1)
	expectedArgList = append(expectedArgList, test2)

	argList := genArgList(&args)

	// Sort both lists so that we can compare them.
	sort.Strings(expectedArgList[0:runIndex])
	sort.Strings(argList[0:runIndex])
	sort.Strings(expectedArgList[runIndex+1 : dutIndex])
	sort.Strings(argList[runIndex+1 : dutIndex])

	if diff := cmp.Diff(argList, expectedArgList, cmp.AllowUnexported(runArgs{})); diff != "" {
		t.Errorf("Got unexpected argument from genArgList (-got %v +want %v):\n%s", argList, expectedArgList, diff)
	}
}

// TestGenArgListWithServers makes sure genArgList generates the correct list of argument for tast
// when various servers are defined.
func TestGenArgListWithServers(t *testing.T) {
	primary := &device.DutInfo{
		Addr:            dut1,
		Role:            "",
		Servo:           "servo0",
		DutServer:       "dutserver0",
		LibsServer:      "libsserver0",
		ProvisionServer: "provisionserver0",
	}
	companions := []*device.DutInfo{
		{
			Addr:            "companion_dut1_address",
			Role:            "cd1",
			Servo:           "servo1",
			DutServer:       "dutserver1",
			ProvisionServer: "provisionserver1",
		},
		{
			Addr:            "companion_dut2_address",
			Role:            "cd2",
			Servo:           "servo2",
			DutServer:       "dutserver2",
			ProvisionServer: "provisionserver2",
		},
	}
	args := runArgs{
		primary:  primary,
		patterns: []string{test1, test2},
		tastFlags: map[string]string{
			verboseFlag: "true",
			logTimeFlag: "false",
		},
		runFlags: map[string]string{
			sshRetriesFlag:             "2",
			testRetriesFlag:            "2",
			downloadDataFlag:           "batch",
			buildFlag:                  "false",
			downloadPrivateBundlesFlag: "true",
			resultsDirFlag:             workDir1,
			reportsServerFlag:          "127.0.0.1:3333",
		},
		companions: companions,
	}

	var expectedArgList []string
	for key, value := range args.tastFlags {
		expectedArgList = append(expectedArgList, fmt.Sprintf("%v=%v", key, value))
	}
	runIndex := len(expectedArgList)
	expectedArgList = append(expectedArgList, "run")
	for key, value := range args.runFlags {
		expectedArgList = append(expectedArgList, fmt.Sprintf("%v=%v", key, value))
	}
	for i, c := range companions {
		expectedArgList = append(expectedArgList, fmt.Sprintf("%v=cd%v:%v", companionDUTFlag, i+1, c.Addr))
	}
	// Creates servo list.
	servoStr := fmt.Sprintf(":%s", primary.Servo)
	for _, c := range companions {
		servoStr = fmt.Sprintf("%s,%s:%s", servoStr, c.Role, c.Servo)
	}
	expectedArgList = append(expectedArgList, fmt.Sprintf("-var=servers.servo=%v", servoStr))
	expectedArgList = append(expectedArgList, fmt.Sprintf("-var=servo=%v", primary.Servo))

	// Creates DUT server list.
	dutServerStr := fmt.Sprintf(":%s", primary.DutServer)
	for _, c := range companions {
		dutServerStr = fmt.Sprintf("%s,%s:%s", dutServerStr, c.Role, c.DutServer)
	}
	expectedArgList = append(expectedArgList, fmt.Sprintf("-var=servers.dut=%v", dutServerStr))

	// Creates Libsserver.
	libsServerStr := fmt.Sprintf(":%s", primary.LibsServer)
	expectedArgList = append(expectedArgList, fmt.Sprintf("-var=servers.libs=%v", libsServerStr))

	// Creates DUT server list.
	ProvisionServerStr := fmt.Sprintf(":%s", primary.ProvisionServer)
	for _, c := range companions {
		ProvisionServerStr = fmt.Sprintf("%s,%s:%s", ProvisionServerStr, c.Role, c.ProvisionServer)
	}
	expectedArgList = append(expectedArgList, fmt.Sprintf("-var=servers.provision=%v", ProvisionServerStr))

	dutIndex := len(expectedArgList)
	expectedArgList = append(expectedArgList, dut1)
	expectedArgList = append(expectedArgList, test1)
	expectedArgList = append(expectedArgList, test2)

	argList := genArgList(&args)

	// Sort both lists so that we can compare them.
	sort.Strings(expectedArgList[0:runIndex])
	sort.Strings(argList[0:runIndex])
	sort.Strings(expectedArgList[runIndex+1 : dutIndex])
	sort.Strings(argList[runIndex+1 : dutIndex])

	if diff := cmp.Diff(argList, expectedArgList, cmp.AllowUnexported(runArgs{})); diff != "" {
		t.Errorf("Got unexpected argument from genArgList (-got %v +want %v):\n%s", argList, expectedArgList, diff)
	}
}

// TestgenHostInfoYAML tests memes.
func TestGenHostInfoYAML(t *testing.T) {
	primary := &device.DutInfo{
		Addr:  "foo",
		Phase: "aphase",
		Sku:   "asku",
		Model: "amodel",
		Board: "aboard",
	}
	expected := make(map[string]string)
	expected["phase"] = primary.Phase
	expected["sku"] = primary.Sku
	expected["model"] = primary.Model
	expected["board"] = primary.Board

	fn, err := genHostInfoYAML(primary)

	if err != nil {
		t.Errorf("Got unexpected err: %v", err)
	}

	fmt.Println(fn)
	defer os.Remove(fn)
	yfile, err := ioutil.ReadFile(fn)

	if err != nil {
		t.Error(err)
	}

	var data Labels
	err = yaml.Unmarshal(yfile, &data)
	if err != nil {
		log.Fatal(err)
	}

	for k, v := range expected {
		testStr := fmt.Sprintf("\"%v:%v\"", k, v)
		if !strings.Contains(data.Autotest_host_info_labels, testStr) {
			t.Errorf("Missing |%v| in: %v", testStr, data.Autotest_host_info_labels)
		}
	}
}