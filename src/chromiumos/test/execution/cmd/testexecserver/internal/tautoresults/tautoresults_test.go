// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tautoresults

import (
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"

	_go "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"

	"github.com/google/go-cmp/cmp"
)

// TestTestsReports verify results can be parsed and returned in the expected fmt.
func TestTestsReports(t *testing.T) {
	testJSON := `
	{"tests":[
	  {
	  "verdict": "Pass",
	  "testname": "infra_pass",
	  "errmsg": ""
	},
	  {
	  "verdict": "Fail",
	  "testname": "infra_fail",
	  "errmsg": "OH NO IT FAILED Q_Q"
	},
	  {
	  "verdict": "Error",
	  "testname": "infra_err",
	  "errmsg": "I drove my car into a tree, and crashed."
	}]
	}`
	td, err := ioutil.TempDir("", "example")
	if err != nil {
		t.Fatal("Failed to create temporary dictectory: ", err)
	}
	defer os.RemoveAll(td)
	fn := filepath.Join(td, "results.json")
	fmt.Println("PRINTING TO FILE")
	fmt.Println(fn)

	f, err := os.Create(fn)
	defer f.Close()

	f.WriteString(testJSON)

	resultsDir := td
	expectedResults := []*api.TestCaseResult{
		{
			TestCaseId: &api.TestCase_Id{Value: "infra_pass_id"},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     filepath.Join(resultsDir),
			},
			Verdict: &api.TestCaseResult_Pass_{Pass: &api.TestCaseResult_Pass{}},
		},
		{
			TestCaseId: &api.TestCase_Id{Value: "infra_fail_id"},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     filepath.Join(resultsDir),
			},
			Verdict: &api.TestCaseResult_Fail_{Fail: &api.TestCaseResult_Fail{}},
		},
		{
			TestCaseId: &api.TestCase_Id{Value: "infra_err_id"},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     filepath.Join(resultsDir),
			},
			Verdict: &api.TestCaseResult_Error_{Error: &api.TestCaseResult_Error{}},
		},
		{
			TestCaseId: &api.TestCase_Id{Value: "infra_dne_id"},
			Verdict:    &api.TestCaseResult_Error_{Error: &api.TestCaseResult_Error{}},
		},
	}

	tests := []string{"infra_pass", "infra_fail", "infra_err", "infra_dne"}

	testNamesToIds := map[string]string{
		"infra_pass": "infra_pass_id",
		"infra_fail": "infra_fail_id",
		"infra_err":  "infra_err_id",
		"infra_dne":  "infra_dne_id",
	}

	reports, err := TestsReports(resultsDir, tests, testNamesToIds)
	if err != nil {
		t.Fatal("Got error from unexpected: ", err)
	}

	if diff := cmp.Diff(reports, expectedResults); diff != "" {
		t.Errorf("Got unexpected reports (-got +want):\n%s", diff)
	}

}

// TestTestsReports_BadJson verify results will be returned as missing if there is no/invalid json.
func TestTestsReports_BadJson(t *testing.T) {
	resultsDir := "fakdir/"
	expectedResults := []*api.TestCaseResult{
		{
			TestCaseId: &api.TestCase_Id{Value: "infra_pass_id"},
			Verdict:    &api.TestCaseResult_Error_{Error: &api.TestCaseResult_Error{}},
		},
		{
			TestCaseId: &api.TestCase_Id{Value: "infra_dne_id"},
			Verdict:    &api.TestCaseResult_Error_{Error: &api.TestCaseResult_Error{}},
		},
	}

	tests := []string{"infra_pass", "infra_dne"}
	testNamesToIds := map[string]string{
		"infra_pass": "infra_pass_id",
		"infra_fail": "infra_fail_id",
		"infra_err":  "infra_err_id",
		"infra_dne":  "infra_dne_id",
	}

	reports, _ := TestsReports(resultsDir, tests, testNamesToIds)

	if diff := cmp.Diff(expectedResults, reports); diff != "" {
		t.Errorf("Got unexpected missing reports (-got +want):\n%s", diff)
	}

}
