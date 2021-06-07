// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tastrpc

import (
	"context"
	"path/filepath"
	"testing"

	"github.com/golang/protobuf/ptypes"
	"github.com/google/go-cmp/cmp"
	_go "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"

	"chromiumos/tast/framework/protocol"
)

func TestReportsServer_LogStream(t *testing.T) {
	const (
		testName1    = "test.Name1"
		logSinkName1 = "tests/name01-20210123/test.Name1/log.txt"
		requestName1 = "request_for_test_name1"
		testLog1a    = "log1a"
		testLog1b    = "log1b"
		testName2    = "test.Name2"
		requestName2 = "request_for_test_name2"
		logSinkName2 = "tests/name01-20210123/test.Name2/log.txt"
		testLog2a    = "log2a"
		resultDir    = "/tmp/tast/results"
	)

	srv, err := NewReportsServer(0, []string{testName1, testName2}, resultDir)
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
	testTime := ptypes.TimestampNow()

	requests := []*protocol.ReportResultRequest{
		{
			Test: "PassedTest",
		},
		{
			Test: "FailedTest",
			Errors: []*protocol.ErrorReport{
				{
					Time:   testTime,
					Reason: "intentionally failed",
					File:   "/tmp/file.go",
					Line:   21,
					Stack:  "None",
				},
			},
		},
		{
			Test:       "SkippedTest",
			SkipReason: "intentally skipped",
		},
	}

	expectedReports := []*api.TestCaseResult{
		{
			TestCaseId:    &api.TestCase_Id{Value: tests[0]},
			ResultDirPath: &_go.StoragePath{Path: filepath.Join(resultDir, "tests", tests[0])},
			Verdict:       &api.TestCaseResult_Pass_{Pass: &api.TestCaseResult_Pass{}},
		},
		{
			TestCaseId:    &api.TestCase_Id{Value: tests[1]},
			ResultDirPath: &_go.StoragePath{Path: filepath.Join(resultDir, "tests", tests[1])},
			Verdict:       &api.TestCaseResult_Fail_{Fail: &api.TestCaseResult_Fail{}},
		},
		{
			TestCaseId:    &api.TestCase_Id{Value: tests[2]},
			ResultDirPath: &_go.StoragePath{Path: filepath.Join(resultDir, "tests", tests[2])},
			Verdict:       &api.TestCaseResult_Error_{Error: &api.TestCaseResult_Error{}},
		},
	}
	expectedMissingReports := []*api.TestCaseResult{
		{
			TestCaseId: &api.TestCase_Id{Value: tests[3]},
			Verdict:    &api.TestCaseResult_Error_{Error: &api.TestCaseResult_Error{}},
		},
	}

	// Setting up reports server and client
	reportsServer, err := NewReportsServer(0, tests, resultDir)
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
		reports := reportsServer.TestsReports()
		if diff := cmp.Diff(reports[i], expectedReports[i]); diff != "" {
			t.Errorf("Got unexpected report from test %q (-got +want):\n%s", expectedReports[i].TestCaseId.Value, diff)
		}
	}

	// Testing for missing reports.
	missingReports := reportsServer.MissingTestsReports()
	if diff := cmp.Diff(missingReports, expectedMissingReports); diff != "" {
		t.Errorf("Got unexpected missing reports (-got +want):\n%s", diff)
	}
}
