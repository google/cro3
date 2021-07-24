// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package tastrpc provides the Tast related RPC services by testexecserver.
package tastrpc

import (
	"context"
	"fmt"
	"net"
	"path/filepath"
	"sync"

	_go "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"

	"chromiumos/tast/framework/protocol"
	"chromiumos/test/execution/errors"
)

// ReportsServer implements the tast.framework.protocol.ReportsServer.
type ReportsServer struct {
	srv          *grpc.Server // RPC server to receive reports from tast.
	listenerAddr net.Addr     // The address for the listener for gRPC service.

	mu sync.Mutex // A mutex to protect reportedTests and testCaseResults.

	tests           []string              // Tests to be run.
	reportedTests   map[string]struct{}   // Tests that have received results.
	testCaseResults []*api.TestCaseResult // Reported test results.
	testResultsDir  string                // Parent directory for all test results.
	testNamesToIds  map[string]string     // Mapping between test names and test ids.
	allErrors       []error               // All errors that has been encountered.
}

var _ protocol.ReportsServer = (*ReportsServer)(nil)

// LogStream gets logs from tast and passes on to progress sink server.
func (s *ReportsServer) LogStream(stream protocol.Reports_LogStreamServer) error {
	// Ignore log for now.
	return nil
}

// ReportResult gets a report request from tast and passes on to progress sink.
func (s *ReportsServer) ReportResult(ctx context.Context, req *protocol.ReportResultRequest) (*protocol.ReportResultResponse, error) {
	testID, ok := s.testNamesToIds[req.Test]
	if !ok {
		s.allErrors = append(s.allErrors, errors.NewStatusError(errors.InvalidArgument,
			fmt.Errorf("failed to find test id for test %v", req.Test)))
		return &protocol.ReportResultResponse{}, nil
	}
	testResult := api.TestCaseResult{
		TestCaseId: &api.TestCase_Id{Value: testID},
		ResultDirPath: &_go.StoragePath{
			HostType: _go.StoragePath_LOCAL,
			Path:     filepath.Join(s.testResultsDir, "tests", req.Test),
		},
		Verdict: &api.TestCaseResult_Pass_{Pass: &api.TestCaseResult_Pass{}},
	}
	if len(req.Errors) > 0 {
		testResult.Verdict = &api.TestCaseResult_Fail_{Fail: &api.TestCaseResult_Fail{}}
	} else if req.SkipReason != "" {
		testResult.Verdict = &api.TestCaseResult_Error_{Error: &api.TestCaseResult_Error{}}
	}

	s.mu.Lock()
	s.reportedTests[req.Test] = struct{}{}
	s.testCaseResults = append(s.testCaseResults, &testResult)
	s.mu.Unlock()

	return &protocol.ReportResultResponse{}, nil
}

// MissingTestsReports return error results to all tests that have not reported results.
func (s *ReportsServer) MissingTestsReports() []*api.TestCaseResult {
	var missingTestResults []*api.TestCaseResult
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, t := range s.tests {
		if _, ok := s.reportedTests[t]; ok {
			continue
		}
		testID, ok := s.testNamesToIds[t]
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

// TestsReports returnd results to all tests that have reported results.
func (s *ReportsServer) TestsReports() []*api.TestCaseResult {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.testCaseResults
}

// Stop stops the ReportsServer.
func (s *ReportsServer) Stop() {
	s.srv.Stop()
}

// Address returns the network address of the ReportsServer.
func (s *ReportsServer) Address() string {
	return s.listenerAddr.String()
}

// Errors returns errors that encountered during test reporting.
func (s *ReportsServer) Errors() []error {
	return s.allErrors
}

// NewReportsServer starts a Reports gRPC service and returns a ReportsServer object when success.
// The caller is responsible for calling Stop() method.
func NewReportsServer(port int, tests []string, testNamesToIds map[string]string, resultDir string) (*ReportsServer, error) {
	l, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
	if err != nil {
		return nil, err
	}
	s := ReportsServer{
		srv:            grpc.NewServer(),
		listenerAddr:   l.Addr(),
		reportedTests:  make(map[string]struct{}),
		tests:          tests,
		testResultsDir: resultDir,
		testNamesToIds: testNamesToIds,
	}

	protocol.RegisterReportsServer(s.srv, &s)
	go s.srv.Serve(l)
	return &s, nil
}
