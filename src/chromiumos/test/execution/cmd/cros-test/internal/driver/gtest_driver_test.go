// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package driver

import (
	"bufio"
	"bytes"
	"fmt"
	"log"
	"math/rand"
	"strings"
	"testing"
	"time"

	"github.com/google/go-cmp/cmp"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/durationpb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// getGtestResult returns a 'passing' result for manipulation
// by a test case.
func getGtestResult() (string, gtestResult) {
	gtestResult := gtestResult{}
	gtestResult.TestSuites = append(gtestResult.TestSuites, gtestSuite{})
	gtestResult.TestSuites[0].TestSuite = append(gtestResult.TestSuites[0].TestSuite, gtestCase{})
	gtestResult.TestSuites[0].TestSuite[0].Classname = "fake"
	gtestResult.TestSuites[0].TestSuite[0].Name = "case1"
	gtestResult.TestSuites[0].TestSuite[0].Status = "RUN"
	gtestResult.TestSuites[0].TestSuite[0].Result = "COMPLETED"
	gtestResult.TestSuites[0].TestSuite[0].Timestamp = time.Now().Format(time.RFC3339)
	gtestResult.TestSuites[0].TestSuite[0].Time = fmt.Sprintf("%ds", rand.Int63n(3600*10)) // Up to 10 hours
	gtestResult.Failures = 0
	gtestResult.Errors = 0
	gtestResult.TestSuites[0].Failures = 0

	caseName := "fake.case1"

	return caseName, gtestResult
}

// TestNewGtestDriver ensures the gtest driver is built correctly
func TestNewGtestDriver(t *testing.T) {
	l := new(log.Logger)

	gtestDriver := NewGtestDriver(l)

	if gtestDriver.logger != l {
		t.Errorf("Got unexpected logger (%v), want (%v)", gtestDriver.logger, l)
	}
}

// TestGtestName ensures the proper name is associated with the driver
func TestGtestName(t *testing.T) {
	const expectedName string = "gtest"

	l := new(log.Logger)

	gtestDriver := NewGtestDriver(l)
	driverName := gtestDriver.Name()
	if diff := cmp.Diff(driverName, expectedName); diff != "" {
		t.Errorf("Got unexpected argument from GtestDriver.Name (-got +want):\n%s\n%v\n--\n%v\n", diff, driverName, expectedName)
	}
}

// TestLogCmdWithData ensures the logCmd function properly
// outputs execution data to the log (with args, etc).
func TestLogCmdWithData(t *testing.T) {
	var logBytes bytes.Buffer
	writer := bufio.NewWriter(&logBytes)

	logger := log.New(writer, "", 0)

	cmd := api.ExecCommandRequest{}
	resp := api.ExecCommandResponse{}

	cmd.Command = "fake command"
	cmd.Args = []string{"arg1", "arg2"}

	resp.ExitInfo = new(api.ExecCommandResponse_ExitInfo)
	resp.ExitInfo.Status = 0
	resp.ExitInfo.ErrorMessage = ""
	resp.Stdout = []byte("Stdout out data")
	resp.Stderr = []byte("Stderr data")

	var expected strings.Builder
	fmt.Fprintf(&expected, "cmd '%v', args '%v'\n", cmd.Command, cmd.Args)
	fmt.Fprintf(&expected, "[status]:\n%v\n", resp.ExitInfo.Status)
	fmt.Fprintf(&expected, "[stdout]:\n%v\n", string(resp.Stdout))
	fmt.Fprintf(&expected, "[stderr]:\n%v\n", string(resp.Stderr))
	fmt.Fprintf(&expected, "[error]:\n%v", resp.ExitInfo.ErrorMessage)

	logCmd(logger, &cmd, &resp)
	writer.Flush()

	actualMsg := logBytes.String()
	expectedMsg := expected.String()

	if diff := cmp.Diff(actualMsg, expectedMsg); diff != "" {
		t.Errorf("logCmd generated unexpected log message (-got +want):\n%s\n%v\n--\n%v\n", diff, actualMsg, expectedMsg)
	}
}

// TestLogCmdWithData ensures the logCmd function properly
// outputs execution data to the log (without args, etc).
func TestLogCmdWithoutData(t *testing.T) {
	var logBytes bytes.Buffer
	writer := bufio.NewWriter(&logBytes)

	logger := log.New(writer, "", 0)

	cmd := api.ExecCommandRequest{}
	resp := api.ExecCommandResponse{}

	cmd.Command = "fake command"

	resp.ExitInfo = new(api.ExecCommandResponse_ExitInfo)
	resp.ExitInfo.Status = 0
	resp.Stdout = []byte{}
	resp.Stderr = []byte{}

	var expected strings.Builder
	fmt.Fprintf(&expected, "cmd '%v', args '%v'", cmd.Command, cmd.Args)
	fmt.Fprintf(&expected, "\n[status]:\n%v", resp.ExitInfo.Status)
	fmt.Fprintf(&expected, "\n[stdout]:\n%v", string(resp.Stdout))
	fmt.Fprintf(&expected, "[stderr]:\n%v", string(resp.Stderr))
	fmt.Fprintf(&expected, "[error]:\n%v", resp.ExitInfo.ErrorMessage)

	logCmd(logger, &cmd, &resp)
	writer.Flush()

	actualMsg := logBytes.String()
	expectedMsg := expected.String()

	if diff := cmp.Diff(actualMsg, expectedMsg); diff != "" {
		t.Errorf("logCmd generated unexpected log message (-got +want):\n%s\n%v\n--\n%v\n", diff, actualMsg, expectedMsg)
	}
}

// TestLogCmdWithExitError ensures the logCmd function properly
// outputs execution data to the log (without args, etc).
func TestLogCmdWithExitError(t *testing.T) {
	var logBytes bytes.Buffer
	writer := bufio.NewWriter(&logBytes)

	logger := log.New(writer, "", 0)

	cmd := api.ExecCommandRequest{}
	resp := api.ExecCommandResponse{}

	cmd.Command = "fake command"

	resp.ExitInfo = new(api.ExecCommandResponse_ExitInfo)
	resp.ExitInfo.Status = 0
	resp.ExitInfo.ErrorMessage = "fake error"
	resp.Stdout = []byte{}
	resp.Stderr = []byte{}

	var expected strings.Builder
	fmt.Fprintf(&expected, "cmd '%v', args '%v'", cmd.Command, cmd.Args)
	fmt.Fprintf(&expected, "\n[status]:\n%v", resp.ExitInfo.Status)
	fmt.Fprintf(&expected, "\n[stdout]:\n%v", string(resp.Stdout))
	fmt.Fprintf(&expected, "[stderr]:\n%v", string(resp.Stderr))
	fmt.Fprintf(&expected, "[error]:\n%v\n", resp.ExitInfo.ErrorMessage)

	logCmd(logger, &cmd, &resp)
	writer.Flush()

	actualMsg := logBytes.String()
	expectedMsg := expected.String()

	if diff := cmp.Diff(actualMsg, expectedMsg); diff != "" {
		t.Errorf("logCmd generated unexpected log message (-got +want):\n%s\n%v\n--\n%v\n", diff, actualMsg, expectedMsg)
	}
}

// TestResultNoSuites ensures that testResult behaves properly
// with no suites in results data.
func TestResultNoSuites(t *testing.T) {
	var result *executionData
	caseName, gtestResult := getGtestResult()

	gtestSuites := gtestResult.TestSuites
	gtestResult.TestSuites = []gtestSuite(nil)

	startTime := time.Now()

	// Check that no suites leads to error.
	if result = testResult(caseName, startTime, &gtestResult); len(result.reasons) == 0 {
		t.Error("expected failure but got pass with no suites specified")
	}

	expectedReasons := 1
	actualReasons := len(result.reasons)

	if diff := cmp.Diff(actualReasons, expectedReasons); diff != "" {
		t.Errorf("unexpected number of reasons (-got +want):\n%s\n%v\n--\n%v\n", diff, actualReasons, expectedReasons)
	}

	// Check that top level suite is there, but no
	// test cases.
	gtestResult.TestSuites = gtestSuites
	gtestResult.TestSuites = append(gtestResult.TestSuites, gtestSuite{})
	if result = testResult("", startTime, &gtestResult); len(result.reasons) == 0 {
		t.Error("expected failure but got pass with no test cases specified")
	}

	actualReasons = len(result.reasons)
	if diff := cmp.Diff(actualReasons, expectedReasons); diff != "" {
		t.Errorf("unexpected number of reasons (-got +want):\n%s\n%v\n--\n%v\n", diff, actualReasons, expectedReasons)
	}
}

// TestResultTestCaseName ensures that validity checks around
// test case name are valid
func TestResultTestCaseName(t *testing.T) {
	var result *executionData
	startTime := time.Now()

	_, gtestResult := getGtestResult()
	testCaseName := "fake.case"

	if result = testResult(testCaseName, startTime, &gtestResult); len(result.reasons) == 0 {
		t.Error("expected failure but got pass with invalid test case specified")
	}

	actualReasons := len(result.reasons)
	expectedReasons := 1
	if diff := cmp.Diff(actualReasons, expectedReasons); diff != "" {
		t.Errorf("unexpected number of reasons (-got +want):\n%s\n%v\n--\n%v\n", diff, actualReasons, expectedReasons)
	}
}

// TestResultEmptyTestCaseName ensures that validity checks around
// test case name are valid when name is empty string
func TestResultEmptyTestCaseName(t *testing.T) {
	var result *executionData
	startTime := time.Now()

	_, gtestResult := getGtestResult()
	testCaseName := ""

	if result = testResult(testCaseName, startTime, &gtestResult); len(result.reasons) == 0 {
		t.Error("expected failure but got pass with invalid test case name specified")
	}

	actualReasons := len(result.reasons)
	expectedReasons := 1
	if diff := cmp.Diff(actualReasons, expectedReasons); diff != "" {
		t.Errorf("unexpected number of reasons (-got +want):\n%s\n%v\n--\n%v\n", diff, actualReasons, expectedReasons)
	}
}

// TestResultTestClassName ensures that validity checks around
// test class name are valid
func TestResultTestClassName(t *testing.T) {
	var result *executionData
	startTime := time.Now()

	_, gtestResult := getGtestResult()
	testCaseName := "fake1.case_nothing"

	if result = testResult(testCaseName, startTime, &gtestResult); len(result.reasons) == 0 {
		t.Error("expected failure but got pass with invalid test case specified")
	}

	actualReasons := len(result.reasons)
	expectedReasons := 1
	if diff := cmp.Diff(actualReasons, expectedReasons); diff != "" {
		t.Errorf("unexpected number of reasons (-got +want):\n%s\n%v\n--\n%v\n", diff, actualReasons, expectedReasons)
	}
}

// TestResultRunResult ensures that validity checks around
// status are valid
func TestResultRunResultStatus(t *testing.T) {
	var result *executionData
	startTime := time.Now()

	testCaseName, gtestResult := getGtestResult()

	gtestResult.TestSuites[0].TestSuite[0].Status = "NOT_RUN"

	if result = testResult(testCaseName, startTime, &gtestResult); len(result.reasons) == 0 {
		t.Error("expected failure but got pass with invalid status value")
	}

	actualReasons := len(result.reasons)
	expectedReasons := 1
	if diff := cmp.Diff(actualReasons, expectedReasons); diff != "" {
		t.Errorf("unexpected number of reasons (-got +want):\n%s\n%v\n--\n%v\n", diff, actualReasons, expectedReasons)
	}
}

// TestResultRunStatus ensures that validity checks around
// Result are valid
func TestResultRunResultResult(t *testing.T) {
	var result *executionData
	startTime := time.Now()

	testCaseName, gtestResult := getGtestResult()

	gtestResult.TestSuites[0].TestSuite[0].Result = "NOT_COMPLETED"

	if result = testResult(testCaseName, startTime, &gtestResult); len(result.reasons) == 0 {
		t.Error("expected failure but got pass with invalid result value")
	}

	actualReasons := len(result.reasons)
	expectedReasons := 1
	if diff := cmp.Diff(actualReasons, expectedReasons); diff != "" {
		t.Errorf("unexpected number of reasons (-got +want):\n%s\n%v\n--\n%v\n", diff, actualReasons, expectedReasons)
	}
}

// TestResultFailures ensures that reason list building is valid
func TestResultSingleFailure(t *testing.T) {
	var result *executionData
	startTime := time.Now()

	testCaseName, gtestResult := getGtestResult()
	failure := gtestFailure{
		Failure: "failure one",
		Type:    "some type",
	}
	gtestResult.TestSuites[0].TestSuite[0].Failures = append(gtestResult.TestSuites[0].TestSuite[0].Failures, failure)

	if result = testResult(testCaseName, startTime, &gtestResult); len(result.reasons) == 0 {
		t.Errorf("passing result when failure expected")
	}

	expectedReasons := []string{fmt.Sprintf("failure: '%v', type: '%v'", failure.Failure, failure.Type)}

	if diff := cmp.Diff(result.reasons, expectedReasons); diff != "" {
		t.Errorf("unexpected result for 'reasons' (-got +want):\n%s\n%v\n--\n%v\n", diff, result.reasons, expectedReasons)
	}
}

// TestResultMultipleFailures ensures that reason list building is valid
func TestResultMultipleFailures(t *testing.T) {
	var result *executionData
	startTime := time.Now()

	testCaseName, gtestResult := getGtestResult()
	failures := []gtestFailure{
		{
			Failure: "failure one",
			Type:    "some type",
		},
		{
			Failure: "failure two",
			Type:    "some type two",
		},
		{
			Failure: "failure three",
			Type:    "some type three",
		},
	}
	gtestResult.TestSuites[0].TestSuite[0].Failures = failures

	if result = testResult(testCaseName, startTime, &gtestResult); len(result.reasons) == 0 {
		t.Errorf("passing result when failure expected")
	}

	expectedReasons := []string{}
	for _, failure := range failures {
		expectedReasons = append(expectedReasons, fmt.Sprintf("failure: '%v', type: '%v'", failure.Failure, failure.Type))
	}

	if diff := cmp.Diff(result.reasons, expectedReasons); diff != "" {
		t.Errorf("unexpected result for 'reasons' (-got +want):\n%s\n%v\n--\n%v\n", diff, result.reasons, expectedReasons)
	}
}

// TestResultUnexpectedFailures ensures that validity checks around
// unexpected gtest failures are valid
func TestResultUnexpectedFailures(t *testing.T) {
	var result *executionData
	startTime := time.Now()

	testCaseName, gtestResult := getGtestResult()

	gtestResult.Failures = 1

	if result = testResult(testCaseName, startTime, &gtestResult); len(result.reasons) == 0 {
		t.Error("expected failure but got pass with unexpected failures")
	}

	actualReasons := len(result.reasons)
	expectedReasons := 1
	if diff := cmp.Diff(actualReasons, expectedReasons); diff != "" {
		t.Errorf("unexpected number of reasons (-got +want):\n%s\n%v\n--\n%v\n", diff, actualReasons, expectedReasons)
	}
}

// TestResultUnexpectedErrors ensures that validity checks around
// unexpected gtest errrors are valid
func TestResultUnexpectedErrors(t *testing.T) {
	var result *executionData
	startTime := time.Now()

	testCaseName, gtestResult := getGtestResult()

	gtestResult.Errors = 1

	if result = testResult(testCaseName, startTime, &gtestResult); len(result.reasons) == 0 {
		t.Error("expected failure but got pass with unexpected errors")
	}

	actualReasons := len(result.reasons)
	expectedReasons := 1
	if diff := cmp.Diff(actualReasons, expectedReasons); diff != "" {
		t.Errorf("unexpected number of reasons (-got +want):\n%s\n%v\n--\n%v\n", diff, actualReasons, expectedReasons)
	}
}

// TestResultUnexpectedSuiteFailures ensures that validity checks around
// unexpected gtest suite failures are valid
func TestResultUnexpectedSuiteFailures(t *testing.T) {
	var result *executionData
	startTime := time.Now()

	testCaseName, gtestResult := getGtestResult()

	gtestResult.TestSuites[0].Failures = 1

	if result = testResult(testCaseName, startTime, &gtestResult); len(result.reasons) == 0 {
		t.Error("expected failure but got pass with unexpected suite failure")
	}

	actualReasons := len(result.reasons)
	expectedReasons := 1
	if diff := cmp.Diff(actualReasons, expectedReasons); diff != "" {
		t.Errorf("unexpected number of reasons (-got +want):\n%s\n%v\n--\n%v\n", diff, actualReasons, expectedReasons)
	}
}

// TestResultUnexpectedSuiteDisabled ensures that validity checks around
// unexpected gtest suite disabled are valid
func TestResultUnexpectedSuiteDisabled(t *testing.T) {
	var result *executionData
	startTime := time.Now()

	testCaseName, gtestResult := getGtestResult()

	gtestResult.TestSuites[0].Disabled = 1

	if result = testResult(testCaseName, startTime, &gtestResult); len(result.reasons) == 0 {
		t.Error("expected failure but got pass with unexpected suite disabled")
	}

	actualReasons := len(result.reasons)
	expectedReasons := 1
	if diff := cmp.Diff(actualReasons, expectedReasons); diff != "" {
		t.Errorf("unexpected number of reasons (-got +want):\n%s\n%v\n--\n%v\n", diff, actualReasons, expectedReasons)
	}
}

// TestResultPass ensures that validity checks around
// for passing tests
func TestResultPass(t *testing.T) {
	var result *executionData
	startTime := time.Now()

	testCaseName, gtestResult := getGtestResult()

	if result = testResult(testCaseName, startTime, &gtestResult); len(result.reasons) != 0 {
		t.Error("unexpected failure when expecting pass")
	}

	expectedReasons := []string(nil)
	if diff := cmp.Diff(result.reasons, expectedReasons); diff != "" {
		t.Errorf("unexpected result for 'reasons' (-got +want):\n%s\n%v\n--\n%v\n", diff, result.reasons, expectedReasons)
	}
}

// TestBadTime ensures that an unparseable time value is handled
// correctly
func TestBadTime(t *testing.T) {
	var result *executionData
	startTime := time.Now()

	testCaseName, gtestResult := getGtestResult()
	gtestResult.TestSuites[0].TestSuite[0].Time = "this isn't a time"

	if result = testResult(testCaseName, startTime, &gtestResult); len(result.reasons) == 0 {
		t.Error("unexpected pass when expecting failure")
	}

	if result.duration != invalidDuration {
		t.Errorf("Unexpected value for duration, want '%d', got '%d'", invalidDuration, result.duration)
	}
}

// TestBadTimestamp ensures that an unparseable time value is handled
// correctly
func TestBadTimestamp(t *testing.T) {
	var result *executionData
	startTime := time.Now()

	testCaseName, gtestResult := getGtestResult()
	gtestResult.TestSuites[0].TestSuite[0].Timestamp = "this isn't a time"

	if result = testResult(testCaseName, startTime, &gtestResult); len(result.reasons) == 0 {
		t.Error("unexpected pass when expecting failure")
	}
}

// TestBuiltTestCaseResultsPass ensures passing results
// proto generation is correct.
func TestBuiltTestCaseResultsPass(t *testing.T) {
	expectedResult := new(api.TestCaseResult)
	tcID := "gtest.fake.test"
	startTime := time.Now()
	reasons := []string{}
	duration := int64(100)

	result := newExecutionData(startTime, duration, reasons)

	expectedResult.TestCaseId = &api.TestCase_Id{Value: tcID}
	expectedResult.Verdict = &api.TestCaseResult_Pass_{Pass: &api.TestCaseResult_Pass{}}
	expectedResult.Reason = strings.Join(reasons, "\n")
	expectedResult.TestHarness = &api.TestHarness{TestHarnessType: &api.TestHarness_Gtest_{Gtest: &api.TestHarness_Gtest{}}}
	expectedResult.StartTime = timestamppb.New(startTime)
	expectedResult.Duration = &durationpb.Duration{Seconds: duration}

	actualResult := buildTestCaseResults(tcID, result)

	if !proto.Equal(actualResult, expectedResult) {
		t.Errorf("unexpected test results for 'pass' (-got +want):\n%v\n--\n%v\n", actualResult, expectedResult)
	}
}

// TestBuiltTestCaseResultsFailSingleReason ensures results struct
// is properly built with a single reason failure
func TestBuiltTestCaseResultsFailSingleReason(t *testing.T) {
	expectedResult := new(api.TestCaseResult)
	tcID := "gtest.fake.test"

	startTime := time.Now()
	reasons := []string{
		"fake reason",
	}
	duration := int64(319)

	result := newExecutionData(startTime, duration, reasons)

	expectedResult.TestCaseId = &api.TestCase_Id{Value: tcID}
	expectedResult.Verdict = &api.TestCaseResult_Fail_{Fail: &api.TestCaseResult_Fail{}}
	expectedResult.Reason = strings.Join(reasons, "\n")
	expectedResult.TestHarness = &api.TestHarness{TestHarnessType: &api.TestHarness_Gtest_{Gtest: &api.TestHarness_Gtest{}}}
	expectedResult.Duration = &durationpb.Duration{Seconds: duration}
	expectedResult.StartTime = timestamppb.New(startTime)

	actualResult := buildTestCaseResults(tcID, result)

	if !proto.Equal(actualResult, expectedResult) {
		t.Errorf("unexpected test results for 'pass' (-got +want):\n%v\n--\n%v\n", actualResult, expectedResult)
	}
}

// TestBuiltTestCaseResultsFailMultipleReason ensures results struct
// is properly built with a multiple reason failure
func TestBuiltTestCaseResultsFailMultipleReason(t *testing.T) {
	expectedResult := new(api.TestCaseResult)
	tcID := "gtest.fake.test"

	startTime := time.Now()
	reasons := []string{
		"fake reason",
		"fake reason 2",
	}
	duration := int64(968)

	result := newExecutionData(startTime, duration, reasons)

	expectedResult.TestCaseId = &api.TestCase_Id{Value: tcID}
	expectedResult.Verdict = &api.TestCaseResult_Fail_{Fail: &api.TestCaseResult_Fail{}}
	expectedResult.Reason = strings.Join(reasons, "\n")
	expectedResult.TestHarness = &api.TestHarness{TestHarnessType: &api.TestHarness_Gtest_{Gtest: &api.TestHarness_Gtest{}}}
	expectedResult.Duration = &durationpb.Duration{Seconds: duration}
	expectedResult.StartTime = timestamppb.New(startTime)

	actualResult := buildTestCaseResults(tcID, result)

	if !proto.Equal(actualResult, expectedResult) {
		t.Errorf("unexpected test results for 'pass' (-got +want):\n%v\n--\n%v\n", actualResult, expectedResult)
	}
}
