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

// TestNewTautoArgs makes sure newTastArgs creates the correct arguments for tast.
func TestNewTautoArgs(t *testing.T) {
	expectedArgs := tautoRunArgs{
		target:   dut1,
		patterns: []string{test1, test2, test3, test4, test5},
		runFlags: map[string]string{
			tautoResultsDirFlag: workDir1,
			autotestDir:         "/usr/local/autotest/",
		},
	}

	dut := dut1
	tests := []string{test1, test2, test3, test4, test5}
	args := newTautoArgs(dut, tests, workDir1)
	if diff := cmp.Diff(args, &expectedArgs, cmp.AllowUnexported(tautoRunArgs{})); diff != "" {
		t.Errorf("Got unexpected argument from newTautoArgs (-got +want):\n%s", diff)
	}
}

// TestGenTautoArgList makes sure genTautoArgList generates the correct list of argument for tast.
func TestGenTautoArgList(t *testing.T) {
	args := tautoRunArgs{
		target:   dut1,
		patterns: []string{test1, test2},
		runFlags: map[string]string{
			tautoResultsDirFlag: workDir1,
			autotestDir:         "/usr/local/autotest/",
		},
	}

	var expectedArgList []string

	runIndex := len(expectedArgList)
	for key, value := range args.runFlags {
		expectedArgList = append(expectedArgList, fmt.Sprintf("%v=%v", key, value))
	}
	dutIndex := len(expectedArgList)
	expectedArgList = append(expectedArgList, dut1)
	expectedArgList = append(expectedArgList, test1)
	expectedArgList = append(expectedArgList, test2)

	argList := genTautoArgList(&args)

	// Sort both lists so that we can compare them.
	sort.Sort(sort.StringSlice(expectedArgList[0:runIndex]))
	sort.Sort(sort.StringSlice(argList[0:runIndex]))
	sort.Sort(sort.StringSlice(expectedArgList[runIndex+1 : dutIndex]))
	sort.Sort(sort.StringSlice(argList[runIndex+1 : dutIndex]))

	if diff := cmp.Diff(argList, expectedArgList, cmp.AllowUnexported(tautoRunArgs{})); diff != "" {
		t.Errorf("Got unexpected argument from genTautoArgList (-got %v +want %v):\n%s", argList, expectedArgList, diff)
	}
}
