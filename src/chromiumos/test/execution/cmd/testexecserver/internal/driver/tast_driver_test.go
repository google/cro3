// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package driver

import (
	"fmt"
	"sort"
	"testing"

	"github.com/google/go-cmp/cmp"
)

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
			downloadPrivateBundlesFlag: "true",
			timeOutFlag:                "3000",
			resultsDirFlag:             workDir1,
			reportsServer:              ":5555",
			tlwServerFlag:              tlwAddress,
		},
	}

	args := newTastArgs(dut1, expectedArgs.patterns, workDir1, tlwAddress, expectedArgs.runFlags[reportsServer])
	if diff := cmp.Diff(args, &expectedArgs, cmp.AllowUnexported(runArgs{})); diff != "" {
		t.Errorf("Got unexpected argument from newTastArgs (-got +want):\n%s\n%v\n--\n%v\n", diff, args, expectedArgs)
	}
}

// TestNewTastArgsNoTlw makes sure newTastArgs creates the correct arguments for tast when no tlw address is specified.
func TestNewTastArgsNoTlw(t *testing.T) {
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
			reportsServer:              ":5555",
			tlwServerFlag:              "",
		},
	}

	args := newTastArgs(dut1, expectedArgs.patterns, workDir1, "", expectedArgs.runFlags[reportsServer])
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
			downloadPrivateBundlesFlag: "true",
			timeOutFlag:                "3000",
			resultsDirFlag:             workDir1,
			tlwServerFlag:              tlwAddress,
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
