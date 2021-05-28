// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package driver

import (
	"fmt"
	"sort"
	"testing"

	"github.com/google/go-cmp/cmp"

	"go.chromium.org/chromiumos/config/go/test/api"
)

// Common test data for multiple tests.
const (
	reqName1   = "PassedTest1"
	reqName2   = "SkippedTest1"
	reqName3   = "PassedTest2"
	reqName4   = "SkippedTest2"
	reqName5   = "FailedTest1"
	suite1     = "suite1"
	suite2     = "suite2"
	test1      = "launcher.PinAppToShelf.clamshell_mode"
	test2      = "launcher.PinAppToShelf.tablet_mode"
	test3      = "launcher.CreateAndRenameFolder.clamshell_mode"
	test4      = "launcher.CreateAndRenameFolder.tablet_mode"
	test5      = "meta.LocalFail"
	workDir1   = "/tmp/tast/result1"
	workDir2   = "/tmp/tast/result2"
	sinkPort   = 22
	tlsAddress = "192.168.86.81"
	tlsPort    = 2227
	tlwAddress = "192.168.86.109"
	tlwPort    = 2228
	dut1       = "127.0.0.1:2222"
)

var req = api.RunTestsRequest{
	TestSuites: []*api.TestSuite{
		{
			Name: suite1,
			TestCaseIds: &api.TestCaseIdList{
				TestCaseIds: []*api.TestCase_Id{
					{
						Value: test1,
					},
					{
						Value: test2,
					},
					{
						Value: test3,
					},
				},
			},
		},
		{
			Name: suite2,
			TestCaseIds: &api.TestCaseIdList{
				TestCaseIds: []*api.TestCase_Id{
					{
						Value: test4,
					},
					{
						Value: test5,
					},
				},
			},
		},
	},
	Dut: &api.DeviceInfo{
		PrimaryHost: dut1,
	},
}

// TestNewTastArgs makes sure newTastArgs creates the correct arguments for tast.
func TestNewTastArgs(t *testing.T) {
	expectedArgs := runArgs{
		target:   dut1,
		patterns: []string{test1, test2, test3, test4, test5},
		tastFlags: map[string]string{
			verboseFlag: "true",
			logTimeFlag: "false",
		},
		runFlags: map[string]string{
			sshRetriesFlag:             "2",
			downloadDataFlag:           "batch",
			buildFlag:                  "false",
			downloadPrivateBundlesFlag: "false",
			timeOutFlag:                "3000",
			resultsDirFlag:             workDir1,
		},
	}

	args := newTastArgs(&req, workDir1)
	if diff := cmp.Diff(args, &expectedArgs, cmp.AllowUnexported(runArgs{})); diff != "" {
		t.Errorf("Got unexpected argument from newTastArgs (-got +want):\n%s", diff)
	}
}

// TestGenArgList makes sure genArgList generates the correct list of argument for tast.
func TestGenArgList(t *testing.T) {
	args := runArgs{
		target:   dut1,
		patterns: []string{test1, test2},
		tastFlags: map[string]string{
			verboseFlag: "true",
			logTimeFlag: "false",
		},
		runFlags: map[string]string{
			sshRetriesFlag:             "2",
			downloadDataFlag:           "batch",
			buildFlag:                  "false",
			downloadPrivateBundlesFlag: "false",
			timeOutFlag:                "3000",
			resultsDirFlag:             workDir1,
			tlwServerFlag:              fmt.Sprintf("%v:%v", tlwAddress, tlwPort),
			reportsServer:              "127.0.0.1:3333",
		},
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
	dutIndex := len(expectedArgList)
	expectedArgList = append(expectedArgList, dut1)
	expectedArgList = append(expectedArgList, test1)
	expectedArgList = append(expectedArgList, test2)

	argList := genArgList(&args)

	// Sort both lists so that we can compare them.
	sort.Sort(sort.StringSlice(expectedArgList[0:runIndex]))
	sort.Sort(sort.StringSlice(argList[0:runIndex]))
	sort.Sort(sort.StringSlice(expectedArgList[runIndex+1 : dutIndex]))
	sort.Sort(sort.StringSlice(argList[runIndex+1 : dutIndex]))

	if diff := cmp.Diff(argList, expectedArgList, cmp.AllowUnexported(runArgs{})); diff != "" {
		t.Errorf("Got unexpected argument from genArgList (-got %v +want %v):\n%s", argList, expectedArgList, diff)
	}
}
