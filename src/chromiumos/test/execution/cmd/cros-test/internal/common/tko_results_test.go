// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"fmt"

	"testing"
	"time"

	"github.com/golang/protobuf/ptypes"

	_go "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
)

// TestTestsReports verify results can be parsed and returned in the expected fmt.
func TestTestsReports(t *testing.T) {

	EXPECTSTARTTIME, err := ptypes.TimestampProto(time.Unix(1670923418, 0))
	if err != nil {
		fmt.Printf("!!!! ERR %v", err)
	}
	DURATION105 := ptypes.DurationProto(time.Second * time.Duration(105))

	testResults := []*api.TestCaseResult{
		{
			TestCaseId: &api.TestCase_Id{Value: "tast.pass"},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     "/tmp/test/results/tast/foo/pass/full.txt",
			},
			Verdict: &api.TestCaseResult_Pass_{Pass: &api.TestCaseResult_Pass{}},
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
		},
		{
			TestCaseId: &api.TestCase_Id{Value: "tast.fail"},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     "/tmp/test/results/tast/foo/fail/full.txt",
			},
			Verdict: &api.TestCaseResult_Fail_{Fail: &api.TestCaseResult_Fail{}},
			Reason:  "tast failed.",
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
			StartTime: EXPECTSTARTTIME,
			Duration:  DURATION105,
		},
		{
			TestCaseId: &api.TestCase_Id{Value: "tast.crash"},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     "/tmp/test/results/tast/foo/crash/full.txt",
			},
			Verdict: &api.TestCaseResult_Crash_{Crash: &api.TestCaseResult_Crash{}},
			Reason:  "I drove my car into a tree, and crashed.",
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
			StartTime: EXPECTSTARTTIME,
			Duration:  DURATION105,
		},
		{
			TestCaseId: &api.TestCase_Id{Value: "tast.notrun"},
			Verdict:    &api.TestCaseResult_NotRun_{NotRun: &api.TestCaseResult_NotRun{}},
			Reason:     "test not scheduled",
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
			StartTime: EXPECTSTARTTIME,
			Duration:  DURATION105,
		},
		{
			TestCaseId: &api.TestCase_Id{Value: "tast.skip"},
			Verdict:    &api.TestCaseResult_Skip_{Skip: &api.TestCaseResult_Skip{}},
			Reason:     "missing dep",
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
			StartTime: EXPECTSTARTTIME,
			Duration:  DURATION105,
		},

		{
			TestCaseId: &api.TestCase_Id{Value: "tast.abort"},
			Verdict:    &api.TestCaseResult_Abort_{Abort: &api.TestCaseResult_Abort{}},
			Reason:     "left for dinner, aborted",
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
			StartTime: EXPECTSTARTTIME,
			Duration:  DURATION105,
		},
	}

	var expectedContent []string

	expectedContent = append(expectedContent, "START	----	tast.pass	timestamp=1671046609	localtime=Dec 14 19:36:49	\n")
	expectedContent = append(expectedContent, "	PASS	----	tast.pass	timestamp=1671046609	localtime=Dec 14 19:36:49	\n")
	expectedContent = append(expectedContent, "END PASS	----	tast.pass	timestamp=1671046609	localtime=Dec 14 19:36:49	\n")
	expectedContent = append(expectedContent, "START	----	tast.fail	timestamp=1670923418	localtime=Dec 13 09:23:38	\n")
	expectedContent = append(expectedContent, "	FAIL	----	tast.fail	timestamp=1670923523	localtime=Dec 13 09:25:23	tast failed.\n")
	expectedContent = append(expectedContent, "END FAIL	----	tast.fail	timestamp=1670923523	localtime=Dec 13 09:25:23	\n")
	expectedContent = append(expectedContent, "START	----	tast.crash	timestamp=1670923418	localtime=Dec 13 09:23:38	\n")
	expectedContent = append(expectedContent, "	FAIL	----	tast.crash	timestamp=1670923523	localtime=Dec 13 09:25:23	I drove my car into a tree, and crashed.\n")
	expectedContent = append(expectedContent, "END FAIL	----	tast.crash	timestamp=1670923523	localtime=Dec 13 09:25:23	\n")
	expectedContent = append(expectedContent, "START	----	tast.notrun	timestamp=1670923418	localtime=Dec 13 09:23:38	\n")
	expectedContent = append(expectedContent, "	NOT_RUN	----	tast.notrun	timestamp=1670923523	localtime=Dec 13 09:25:23	test not scheduled\n")
	expectedContent = append(expectedContent, "END NOT_RUN	----	tast.notrun	timestamp=1670923523	localtime=Dec 13 09:25:23	\n")
	expectedContent = append(expectedContent, "START	----	tast.skip	timestamp=1670923418	localtime=Dec 13 09:23:38	\n")
	expectedContent = append(expectedContent, "	SKIP	----	tast.skip	timestamp=1670923523	localtime=Dec 13 09:25:23	missing dep\n")
	expectedContent = append(expectedContent, "END SKIP	----	tast.skip	timestamp=1670923523	localtime=Dec 13 09:25:23	\n")
	expectedContent = append(expectedContent, "START	----	tast.abort	timestamp=1670923418	localtime=Dec 13 09:23:38	\n")
	expectedContent = append(expectedContent, "	FAIL	----	tast.abort	timestamp=1670923523	localtime=Dec 13 09:25:23	left for dinner, aborted\n")
	expectedContent = append(expectedContent, "END FAIL	----	tast.abort	timestamp=1670923523	localtime=Dec 13 09:25:23	\n")

	content, err := generateTkoLog(testResults, 1671046609)
	if err != nil {
		t.Fatal("Got error from unexpected: ", err)
	}
	fmt.Print(len(content))
	for i, line := range content {
		if line != expectedContent[i] {
			t.Fatal(fmt.Sprintf("\n%s\n!= (Line %d) expected:\n%s\n", line, i+1, expectedContent[i]))
		}
	}

}
