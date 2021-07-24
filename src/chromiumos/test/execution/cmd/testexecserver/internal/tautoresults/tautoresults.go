// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package tautoresults provides test results for Tauto.
package tautoresults

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"path/filepath"

	"chromiumos/test/execution/errors"

	_go "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
)

// Report TODO: probably need to eventually move tauto over from results parsing.
type Report struct {
	tests           []string              // Tests to be run.
	testCaseResults []*api.TestCaseResult // Reported test results.
	testResultsDir  string                // Parent directory for all test results.N
	reportedTests   map[string]struct{}   // Tests that have received results.
	testNamesToIds  map[string]string     // Mapping between test names and test ids.
	RawResults      results
}

// results TODO: Temp structs to support testing autotest result parsing/reporting.
type results struct {
	Tests []test `json:"tests"`
}

// Test mirrors of the test_results.json example.
type test struct {
	Verdict  string `json:"verdict"`
	Testname string `json:"testname"`
	Errmsg   string `json:"errmsg"`
}

// loadJSON unmarshals the json into the Report.RawResults struct.
func (r *Report) loadJSON(resultsDir string) error {
	plan, _ := ioutil.ReadFile(filepath.Join(resultsDir, "results.json"))
	err := json.Unmarshal(plan, &r.RawResults)
	if err != nil {
		return errors.NewStatusError(errors.UnmarshalError,
			fmt.Errorf("failed to unmarshal results: %v From: %v", err, resultsDir))
	}
	return nil
}

// GenerateReport gets a report request from tast and passes on to progress sink.
func GenerateReport(test test, testID string, resultsDir string) *api.TestCaseResult {
	// For now, assume results will be in $results_dir/"test_results.json"
	// Mark the result as found.
	// r.reportedTests[test] = struct{}{}
	testResult := api.TestCaseResult{
		TestCaseId: &api.TestCase_Id{Value: testID},
		ResultDirPath: &_go.StoragePath{
			HostType: _go.StoragePath_LOCAL,
			Path:     filepath.Join(resultsDir),
		},
		Verdict: &api.TestCaseResult_Pass_{Pass: &api.TestCaseResult_Pass{}},
	}

	// Change result to fail/err as needed.
	if test.Verdict == "Fail" {
		testResult.Verdict = &api.TestCaseResult_Fail_{Fail: &api.TestCaseResult_Fail{}}
	} else if test.Verdict == "Error" {
		testResult.Verdict = &api.TestCaseResult_Error_{Error: &api.TestCaseResult_Error{}}
	}
	// r.testCaseResults = append(r.testCaseResults, &testResult)
	return &testResult
}

// MissingTestsReports returns tests not found in the resultsdir, marked as err.
func (r *Report) MissingTestsReports() []*api.TestCaseResult {
	var missingTestResults []*api.TestCaseResult
	for _, t := range r.tests {
		if _, ok := r.reportedTests[t]; ok {
			continue
		}
		testID, ok := r.testNamesToIds[t]
		if !ok {
			continue
		}
		missingTestResults = append(missingTestResults, &api.TestCaseResult{
			TestCaseId: &api.TestCase_Id{Value: testID},
			Verdict:    &api.TestCaseResult_Error_{Error: &api.TestCaseResult_Error{}},
		})
	}
	return missingTestResults
}

// TestsReports returns results to all tests.
func TestsReports(resultsDir string, tests []string, testNamesToIds map[string]string) ([]*api.TestCaseResult, error) {
	report := Report{
		reportedTests:  make(map[string]struct{}),
		tests:          tests,
		testResultsDir: resultsDir,
		testNamesToIds: testNamesToIds,
	}
	report.tests = tests

	err := report.loadJSON(resultsDir)
	if err != nil {
		return append(report.testCaseResults, report.MissingTestsReports()...), err
	}

	for _, test := range report.RawResults.Tests {
		testID, ok := testNamesToIds[test.Testname]
		if !ok {
			return report.testCaseResults, errors.NewStatusError(errors.InvalidArgument,
				fmt.Errorf("failed to find test id for test %v", test.Testname))
		}
		report.reportedTests[test.Testname] = struct{}{}
		report.testCaseResults = append(report.testCaseResults, GenerateReport(test, testID, resultsDir))
	}
	return append(report.testCaseResults, report.MissingTestsReports()...), nil
}
