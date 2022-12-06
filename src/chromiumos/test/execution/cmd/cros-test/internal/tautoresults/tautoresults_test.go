// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tautoresults

import (
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"

	"testing"
	"time"

	"github.com/golang/protobuf/ptypes"
	"google.golang.org/protobuf/proto"

	_go "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
)

// TestTestsReports verify results can be parsed and returned in the expected fmt.
func TestTestsReports(t *testing.T) {
	testJSON := `
	{"tests":[
	  {
	  "verdict": "Pass",
	  "testname": "infra_pass",
	  "errmsg": "",
	  "resultspath": "/tmp/test/results/tauto/results-1-stub_FailServer",
	  "starttime": "1650319391",
	  "endtime": "1650319496"
	},
	  {
	  "verdict": "Fail",
	  "testname": "infra_fail",
	  "errmsg": "OH NO IT FAILED Q_Q",
	  "resultspath": "/tmp/test/results/tauto/results-1-stub_FailServer",
	  "starttime": "1650319391",
	  "endtime": "1650319391"
	},
	  {
	  "verdict": "Error",
	  "testname": "infra_err",
	  "errmsg": "I drove my car into a tree, and crashed.",
	  "resultspath": "/tmp/test/results/tauto/results-1-stub_FailServer",
	  "starttime": "1650319391",
	  "endtime": "1650319496"
	}]
	}`
	td, err := ioutil.TempDir("", "example")
	if err != nil {
		t.Fatal("Failed to create temporary dictectory: ", err)
	}
	defer os.RemoveAll(td)
	fn := filepath.Join(td, "results.json")

	f, err := os.Create(fn)
	defer f.Close()

	f.WriteString(testJSON)

	EXPECTSTARTTIME, err := ptypes.TimestampProto(time.Unix(1650319391, 0))
	if err != nil {
		fmt.Printf("!!!! ERR %v", err)
	}
	DURATION0 := ptypes.DurationProto(time.Second * time.Duration(0))
	DURATION105 := ptypes.DurationProto(time.Second * time.Duration(105))

	resultsDir := td
	expectedResults := []*api.TestCaseResult{
		{
			TestCaseId: &api.TestCase_Id{Value: "infra_pass_id"},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     "/tmp/test/results/tauto/results-1-stub_FailServer",
			},
			Verdict: &api.TestCaseResult_Pass_{Pass: &api.TestCaseResult_Pass{}},
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tauto_{
					Tauto: &api.TestHarness_Tauto{},
				},
			},
			StartTime: EXPECTSTARTTIME,
			Duration:  DURATION105,
		},
		{
			TestCaseId: &api.TestCase_Id{Value: "infra_fail_id"},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     "/tmp/test/results/tauto/results-1-stub_FailServer",
			},
			Verdict: &api.TestCaseResult_Fail_{Fail: &api.TestCaseResult_Fail{}},
			Reason:  "OH NO IT FAILED Q_Q",
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tauto_{
					Tauto: &api.TestHarness_Tauto{},
				},
			},
			StartTime: EXPECTSTARTTIME,
			Duration:  DURATION0,
		},
		{
			TestCaseId: &api.TestCase_Id{Value: "infra_err_id"},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     "/tmp/test/results/tauto/results-1-stub_FailServer",
			},
			Verdict: &api.TestCaseResult_Crash_{Crash: &api.TestCaseResult_Crash{}},
			Reason:  "I drove my car into a tree, and crashed.",
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tauto_{
					Tauto: &api.TestHarness_Tauto{},
				},
			},
			StartTime: EXPECTSTARTTIME,
			Duration:  DURATION105,
		},
		{
			TestCaseId: &api.TestCase_Id{Value: "infra_dne_id"},
			Verdict:    &api.TestCaseResult_NotRun_{NotRun: &api.TestCaseResult_NotRun{}},
			Reason:     "AutoservCrash",
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tauto_{
					Tauto: &api.TestHarness_Tauto{},
				},
			},
		},
	}

	tests := []string{"infra_pass", "infra_fail", "infra_err", "infra_dne"}

	testNamesToIds := map[string]string{
		"infra_pass": "infra_pass_id",
		"infra_fail": "infra_fail_id",
		"infra_err":  "infra_err_id",
		"infra_dne":  "infra_dne_id",
	}

	reports, err := TestsReports(resultsDir, tests, testNamesToIds, "AutoservCrash")
	if err != nil {
		t.Fatal("Got error from unexpected: ", err)
	}

	for i := 0; i < len(reports); i++ {
		if !proto.Equal(reports[i], expectedResults[i]) {
			t.Errorf("Got unexpected reports(-got +want):\n%v\n--\n%v\n", reports, expectedResults)
		}
	}

}

// TestTestsReports_BadJson verify results will be returned as missing if there is no/invalid json.
func TestTestsReports_BadJson(t *testing.T) {
	resultsDir := "fakdir/"
	missingReason := "aReason"

	expectedResults := []*api.TestCaseResult{
		{
			TestCaseId: &api.TestCase_Id{Value: "infra_pass_id"},
			Verdict:    &api.TestCaseResult_NotRun_{NotRun: &api.TestCaseResult_NotRun{}},
			Reason:     missingReason,
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tauto_{
					Tauto: &api.TestHarness_Tauto{},
				},
			},
		},
		{
			TestCaseId: &api.TestCase_Id{Value: "infra_dne_id"},
			Verdict:    &api.TestCaseResult_NotRun_{NotRun: &api.TestCaseResult_NotRun{}},
			Reason:     missingReason,
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tauto_{
					Tauto: &api.TestHarness_Tauto{},
				},
			},
		},
	}

	tests := []string{"infra_pass", "infra_dne"}
	testNamesToIds := map[string]string{
		"infra_pass": "infra_pass_id",
		"infra_fail": "infra_fail_id",
		"infra_err":  "infra_err_id",
		"infra_dne":  "infra_dne_id",
	}

	reports, _ := TestsReports(resultsDir, tests, testNamesToIds, missingReason)

	for i := 0; i < len(reports); i++ {
		if !proto.Equal(reports[i], expectedResults[i]) {
			t.Errorf("Got unexpected reports(-got +want):\n%v\n--\n%v\n", reports, expectedResults)
		}
	}

}

func TestAbortedResults(t *testing.T) {
	testJSON := `
	{"tests": [{"verdict": "Abort", "testname": "stub_ServerToClientPass", "errmsg": "client job was aborted", "resultspath": "/tmp/test/results/tauto/results-1-stub_ServerToClientPass", "starttime": "1670062681", "endtime": "1670062718"}]}`
	td, err := ioutil.TempDir("", "example")
	if err != nil {
		t.Fatal("Failed to create temporary dictectory: ", err)
	}
	defer os.RemoveAll(td)
	fn := filepath.Join(td, "results.json")

	f, err := os.Create(fn)
	defer f.Close()

	f.WriteString(testJSON)

	EXPECTSTARTTIME, err := ptypes.TimestampProto(time.Unix(1670062681, 0))
	if err != nil {
		fmt.Printf("!!!! ERR %v", err)
	}
	DURATION105 := ptypes.DurationProto(time.Second * time.Duration(37))

	resultsDir := td
	expectedResults := []*api.TestCaseResult{
		{
			TestCaseId: &api.TestCase_Id{Value: "stub_ServerToClientPass"},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     "/tmp/test/results/tauto/results-1-stub_ServerToClientPass",
			},
			Verdict: &api.TestCaseResult_Abort_{Abort: &api.TestCaseResult_Abort{}},
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tauto_{
					Tauto: &api.TestHarness_Tauto{},
				},
			},
			Reason:    "client job was aborted",
			StartTime: EXPECTSTARTTIME,
			Duration:  DURATION105,
		},
	}

	tests := []string{"infra_pass", "infra_fail", "infra_err", "infra_dne"}

	testNamesToIds := map[string]string{
		"stub_ServerToClientPass": "stub_ServerToClientPass",
	}

	reports, err := TestsReports(resultsDir, tests, testNamesToIds, "AutoservCrash")
	if err != nil {
		t.Fatal("Got error from unexpected: ", err)
	}

	for i := 0; i < len(reports); i++ {
		if !proto.Equal(reports[i], expectedResults[i]) {
			t.Errorf("Got unexpected reports(-got +want):\n%v\n--\n%v\n", reports, expectedResults)
		}
	}

}

func TestMalformedResults(t *testing.T) {
	testJSON := `
	{"tests": [{"verdict": "UNKOWN", "testname": "stub_ServerToClientPass", "errmsg": "someCrash", "resultspath": "/tmp/test/results/tauto/results-1-stub_ServerToClientPass", "starttime": "1670062681", "endtime": "1670062718"}]}`
	td, err := ioutil.TempDir("", "example")
	if err != nil {
		t.Fatal("Failed to create temporary dictectory: ", err)
	}
	defer os.RemoveAll(td)
	fn := filepath.Join(td, "results.json")

	f, err := os.Create(fn)
	defer f.Close()

	f.WriteString(testJSON)

	EXPECTSTARTTIME, err := ptypes.TimestampProto(time.Unix(1670062681, 0))
	if err != nil {
		fmt.Printf("!!!! ERR %v", err)
	}
	DURATION105 := ptypes.DurationProto(time.Second * time.Duration(37))

	resultsDir := td
	expectedResults := []*api.TestCaseResult{
		{
			TestCaseId: &api.TestCase_Id{Value: "stub_ServerToClientPass"},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     "/tmp/test/results/tauto/results-1-stub_ServerToClientPass",
			},
			Verdict: &api.TestCaseResult_Crash_{Crash: &api.TestCaseResult_Crash{}},
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tauto_{
					Tauto: &api.TestHarness_Tauto{},
				},
			},
			Reason:    "Result status indicator unknown, defaulting to CRASH: someCrash",
			StartTime: EXPECTSTARTTIME,
			Duration:  DURATION105,
		},
	}

	tests := []string{"infra_pass", "infra_fail", "infra_err", "infra_dne"}

	testNamesToIds := map[string]string{
		"stub_ServerToClientPass": "stub_ServerToClientPass",
	}

	reports, err := TestsReports(resultsDir, tests, testNamesToIds, "AutoservCrash")
	if err != nil {
		t.Fatal("Got error from unexpected: ", err)
	}

	for i := 0; i < len(reports); i++ {
		if !proto.Equal(reports[i], expectedResults[i]) {
			t.Errorf("Got unexpected reports(-got +want):\n%v\n--\n%v\n", reports, expectedResults)
		}
	}

}
