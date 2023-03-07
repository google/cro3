// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tastrpc

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"github.com/golang/protobuf/ptypes"
	_go "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"
	"google.golang.org/protobuf/proto"

	"chromiumos/tast/framework/protocol"
)

func TestReportsServer_LogStream(t *testing.T) {
	const (
		testName1    = "test.Name1"
		testID1      = "tast.test.Id1"
		logSinkName1 = "tests/name01-20210123/test.Name1/log.txt"
		requestName1 = "request_for_test_name1"
		testLog1a    = "log1a"
		testLog1b    = "log1b"
		testName2    = "test.Name2"
		testID2      = "tast.test.Id2"
		requestName2 = "request_for_test_name2"
		logSinkName2 = "tests/name01-20210123/test.Name2/log.txt"
		testLog2a    = "log2a"
		resultDir    = "/tmp/tast/results"
	)

	testNamesToIds := map[string]string{
		testName1: testID1,
		testName2: testID2,
	}

	srv, err := NewReportsServer(0, []string{testName1, testName2}, testNamesToIds, resultDir)
	if err != nil {
		t.Fatalf("Failed to start Reports server: %v", err)
	}
	defer srv.Stop()

	conn, err := grpc.Dial(srv.Address(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := protocol.NewReportsClient(conn)
	strm, err := cl.LogStream(context.Background())
	if err != nil {
		t.Fatalf("Failed at LogStream: %v", err)
	}
	if err := strm.Send(&protocol.LogStreamRequest{
		Test:    testName1,
		LogPath: logSinkName1,
		Data:    []byte(testLog1a),
	}); err != nil {
		t.Errorf("failed to send: %v", err)
	}
	if err := strm.Send(&protocol.LogStreamRequest{
		Test:    testName1,
		LogPath: logSinkName1,
		Data:    []byte(testLog1b),
	}); err != nil {
		t.Errorf("failed to send: %v", err)
	}
	if err := strm.Send(&protocol.LogStreamRequest{
		Test:    testName2,
		LogPath: logSinkName2,
		Data:    []byte(testLog2a),
	}); err != nil {
		t.Errorf("failed to send: %v", err)
	}
	strm.CloseAndRecv()
}

// TestReportsServer_ReportResult makes sure reports server will pass on result to progress sink.
func TestReportsServer_ReportResult(t *testing.T) {
	ctx := context.Background()

	resultDir := "/tmp/tast/results"
	tests := []string{
		"PassedTest",
		"FailedTest",
		"SkippedTest",
		"MissingTest", // Used for testing missing test report.
	}
	testIDs := []string{
		"PassedTestId",
		"FailedTestId",
		"SkippedTestId",
		"MissingTestId", // Used for testing missing test report.
	}
	testNamesToIds := map[string]string{
		"PassedTest":  "PassedTestId",
		"FailedTest":  "FailedTestId",
		"SkippedTest": "SkippedTestId",
		"MissingTest": "MissingTestId",
	}
	testTimePassedTest, err := ptypes.TimestampProto(time.Time{})
	if err != nil {
		t.Error("Failed to create start time for PassedTest", err)
	}
	testTimeFailedTest, err := ptypes.TimestampProto(time.Time{}.Add(1))
	if err != nil {
		t.Error("Failed to create start time for FailededTest", err)
	}
	testTimeSkippedTest, err := ptypes.TimestampProto(time.Time{}.Add(2))
	if err != nil {
		t.Error("Failed to create start time for FailedTest", err)
	}

	requests := []*protocol.ReportResultRequest{
		{
			Test:      "PassedTest",
			StartTime: testTimePassedTest,
			Duration:  ptypes.DurationProto(time.Second),
		},
		{
			Test: "FailedTest",
			Errors: []*protocol.ErrorReport{
				{
					Time:   testTimeFailedTest,
					Reason: "intentionally failed",
					File:   "/tmp/file.go",
					Line:   21,
					Stack:  "None",
				},
			},
			StartTime: testTimeFailedTest,
			Duration:  ptypes.DurationProto(time.Second),
		},
		{
			Test:       "SkippedTest",
			SkipReason: "intentionally skipped",
			StartTime:  testTimeSkippedTest,
			Duration:   ptypes.DurationProto(0),
		},
	}

	expectedReports := []*api.TestCaseResult{
		{
			TestCaseId: &api.TestCase_Id{Value: testIDs[0]},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     filepath.Join(resultDir, "tests", tests[0]),
			},
			Verdict: &api.TestCaseResult_Pass_{Pass: &api.TestCaseResult_Pass{}},
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
			StartTime: testTimePassedTest,
			Duration:  ptypes.DurationProto(time.Second),
		},
		{
			TestCaseId: &api.TestCase_Id{Value: testIDs[1]},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     filepath.Join(resultDir, "tests", tests[1]),
			},
			Verdict: &api.TestCaseResult_Fail_{Fail: &api.TestCaseResult_Fail{}},
			Reason:  "intentionally failed",
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
			StartTime: testTimeFailedTest,
			Duration:  ptypes.DurationProto(time.Second),
		},
		{
			TestCaseId: &api.TestCase_Id{Value: testIDs[2]},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     filepath.Join(resultDir, "tests", tests[2]),
			},
			Verdict: &api.TestCaseResult_Skip_{Skip: &api.TestCaseResult_Skip{}},
			Reason:  "intentionally skipped",
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
			StartTime: testTimeSkippedTest,
			Duration:  ptypes.DurationProto(0),
		},
	}
	expectedMissingReports := []*api.TestCaseResult{
		{
			TestCaseId: &api.TestCase_Id{Value: testIDs[3]},
			Verdict:    &api.TestCaseResult_NotRun_{NotRun: &api.TestCaseResult_NotRun{}},
			Reason:     "Test did not run",
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
		},
	}

	// Setting up reports server and client
	reportsServer, err := NewReportsServer(0, tests, testNamesToIds, resultDir)
	if err != nil {
		t.Fatalf("Failed to start Reports server: %v", err)
	}
	defer reportsServer.Stop()
	reportsConn, err := grpc.Dial(reportsServer.Address(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer reportsConn.Close()
	reportsClient := protocol.NewReportsClient(reportsConn)

	// Testing for normal reports.
	for i, r := range requests {
		rspn, err := reportsClient.ReportResult(ctx, r)
		if err != nil {
			t.Fatalf("Failed at ReportResult: %v", err)
		}
		if rspn.Terminate {
			t.Errorf("ReportResult(ctx, %+v) returned true; wanted false", r)
		}
		reportErrors := reportsServer.Errors()
		if len(reportErrors) > 0 {
			t.Fatal("Encountered errors at ReportResult: ", reportErrors)
		}
		reports := reportsServer.TestsReports()
		if !proto.Equal(reports[i], expectedReports[i]) {
			t.Errorf("Got unexpected report from test %q (-got +want):\n%v\n--\n%v\n", expectedReports[i].TestCaseId.Value, reports[i], expectedReports[i])
		}
	}

	// Testing for missing reports.
	missingReports := reportsServer.MissingTestsReports("Test did not run")

	if !proto.Equal(missingReports[0], expectedMissingReports[0]) {
		t.Errorf("unexpected test results for 'pass' (-got +want):\n%v\n--\n%v\n", missingReports[0], expectedMissingReports[0])
	}
}

// TestReportsServer_ReportResult makes sure reports server will pass on result to progress sink.
func TestReportsServer_ReportResultRetry(t *testing.T) {
	ctx := context.Background()

	resultDir := "/tmp/tast/results"
	tests := []string{
		"PassedTest",
		"FailedTest",
		"SkippedTest",
		"MissingTest", // Used for testing missing test report.
	}
	testIDs := []string{
		"PassedTestId",
		"FailedTestId",
		"SkippedTestId",
		"MissingTestId", // Used for testing missing test report.
	}
	testNamesToIds := map[string]string{
		"PassedTest":  "PassedTestId",
		"FailedTest":  "FailedTestId",
		"SkippedTest": "SkippedTestId",
		"MissingTest": "MissingTestId",
	}
	testTimePassedTest, err := ptypes.TimestampProto(time.Time{})
	if err != nil {
		t.Error("Failed to create start time for PassedTest", err)
	}
	testTimeFailedTest, err := ptypes.TimestampProto(time.Time{}.Add(1))
	if err != nil {
		t.Error("Failed to create start time for FailededTest", err)
	}
	testTimeSkippedTest, err := ptypes.TimestampProto(time.Time{}.Add(2))
	if err != nil {
		t.Error("Failed to create start time for FailedTest", err)
	}
	testTimeFailedTestRetry, err := ptypes.TimestampProto(time.Time{}.Add(3))
	if err != nil {
		t.Error("Failed to create start time for FailedTestRetry", err)
	}
	requests := []*protocol.ReportResultRequest{
		{
			Test:      "PassedTest",
			StartTime: testTimePassedTest,
			Duration:  ptypes.DurationProto(time.Second),
		},
		{
			Test: "FailedTest",
			Errors: []*protocol.ErrorReport{
				{
					Time:   testTimeFailedTest,
					Reason: "intentionally failed",
					File:   "/tmp/file.go",
					Line:   21,
					Stack:  "None",
				},
			},
			StartTime: testTimeFailedTest,
			Duration:  ptypes.DurationProto(time.Second),
		},
		{
			Test:       "SkippedTest",
			SkipReason: "intentionally skipped",
			StartTime:  testTimeSkippedTest,
			Duration:   ptypes.DurationProto(0),
		},
		{
			Test:      "FailedTest",
			StartTime: testTimeFailedTestRetry,
			Duration:  ptypes.DurationProto(time.Second),
		},
	}

	expectedReports := []*api.TestCaseResult{
		{
			TestCaseId: &api.TestCase_Id{Value: testIDs[0]},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     filepath.Join(resultDir, "tests", tests[0]),
			},
			Verdict: &api.TestCaseResult_Pass_{Pass: &api.TestCaseResult_Pass{}},
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
			StartTime: testTimePassedTest,
			Duration:  ptypes.DurationProto(time.Second),
		},
		{
			TestCaseId: &api.TestCase_Id{Value: testIDs[2]},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     filepath.Join(resultDir, "tests", tests[2]),
			},
			Verdict: &api.TestCaseResult_Skip_{Skip: &api.TestCaseResult_Skip{}},
			Reason:  "intentionally skipped",
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
			StartTime: testTimeSkippedTest,
			Duration:  ptypes.DurationProto(0),
		},
		{
			TestCaseId: &api.TestCase_Id{Value: testIDs[1]},
			ResultDirPath: &_go.StoragePath{
				HostType: _go.StoragePath_LOCAL,
				Path:     filepath.Join(resultDir, "tests", tests[1]),
			},
			Verdict: &api.TestCaseResult_Pass_{Pass: &api.TestCaseResult_Pass{}},
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
			StartTime: testTimeFailedTestRetry,
			Duration:  ptypes.DurationProto(time.Second),
		},
	}
	expectedMissingReports := []*api.TestCaseResult{
		{
			TestCaseId: &api.TestCase_Id{Value: testIDs[3]},
			Verdict:    &api.TestCaseResult_NotRun_{NotRun: &api.TestCaseResult_NotRun{}},
			Reason:     "Test did not run",
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
		},
	}

	// Setting up reports server and client
	reportsServer, err := NewReportsServer(0, tests, testNamesToIds, resultDir)
	if err != nil {
		t.Fatalf("Failed to start Reports server: %v", err)
	}
	defer reportsServer.Stop()
	reportsConn, err := grpc.Dial(reportsServer.Address(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer reportsConn.Close()
	reportsClient := protocol.NewReportsClient(reportsConn)

	// Testing for normal reports.
	for _, r := range requests {
		rspn, err := reportsClient.ReportResult(ctx, r)
		if err != nil {
			t.Fatalf("Failed at ReportResult: %v", err)
		}
		if rspn.Terminate {
			t.Errorf("ReportResult(ctx, %+v) returned true; wanted false", r)
		}
		reportErrors := reportsServer.Errors()
		if len(reportErrors) > 0 {
			t.Fatal("Encountered errors at ReportResult: ", reportErrors)
		}
	}
	reports := reportsServer.TestsReports()

	for i, report := range reports {
		if !proto.Equal(report, expectedReports[i]) {
			t.Errorf("Got unexpected report from test %q (-got +want):\n%v\n--\n%v\n", expectedReports[i].TestCaseId.Value, reports[i], expectedReports[i])
		}
	}

	// Testing for missing reports.
	missingReports := reportsServer.MissingTestsReports("Test did not run")

	if !proto.Equal(missingReports[0], expectedMissingReports[0]) {
		t.Errorf("unexpected test results for 'pass' (-got +want):\n%v\n--\n%v\n", missingReports[0], expectedMissingReports[0])
	}
}