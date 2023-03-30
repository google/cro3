// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package tastrpc provides the Tast related RPC services by cros-test.
package tastrpc

import (
	"context"
	"fmt"
	"io"
	"net"
	"path/filepath"
	"strings"
	"sync"

	"github.com/golang/protobuf/ptypes/empty"
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

	tests               []string                         // Tests to be run.
	reportedTests       map[string]struct{}              // Tests that have received results.
	testCaseResults     []*api.TestCaseResult            // Reported test results.
	testResultsDir      string                           // Parent directory for all test results.
	testNamesToIds      map[string]string                // Mapping between test names and test ids.
	testNamesToMetadata map[string]*api.TestCaseMetadata // Mapping between test names and test metadata.
	allErrors           []error                          // All errors that has been encountered.
}

var _ protocol.ReportsServer = (*ReportsServer)(nil)

// LogStream gets logs from tast and passes on to progress sink server.
func (s *ReportsServer) LogStream(stream protocol.Reports_LogStreamServer) error {
	for {
		_, err := stream.Recv()
		if err == io.EOF {
			return stream.SendAndClose(&empty.Empty{})
		}
		if err != nil {
			return err
		}
	}
}

// ReportResult gets a report request from tast and passes on to progress sink.
func (s *ReportsServer) ReportResult(ctx context.Context, req *protocol.ReportResultRequest) (*protocol.ReportResultResponse, error) {
	testID, ok := s.testNamesToIds[req.Test]
	if !ok {
		s.allErrors = append(s.allErrors, errors.NewStatusError(errors.InvalidArgument,
			fmt.Errorf("failed to find test id for test %v", req.Test)))
		return &protocol.ReportResultResponse{}, nil
	}
	testMetadata, ok := s.testNamesToMetadata[req.Test]
	if !ok {
		testMetadata = nil
		s.allErrors = append(s.allErrors, errors.NewStatusError(errors.MissingArgument,
			fmt.Errorf("failed to find test metadata for test %v", req.Test)))
	}
	testResult := api.TestCaseResult{
		TestCaseId: &api.TestCase_Id{Value: testID},
		ResultDirPath: &_go.StoragePath{
			HostType: _go.StoragePath_LOCAL,
			Path:     filepath.Join(s.testResultsDir, "tests", req.Test),
		},
		Verdict: &api.TestCaseResult_Pass_{Pass: &api.TestCaseResult_Pass{}},
		TestHarness: &api.TestHarness{
			TestHarnessType: &api.TestHarness_Tast_{
				Tast: &api.TestHarness_Tast{},
			},
		},
		StartTime:        req.StartTime,
		Duration:         req.Duration,
		TestCaseMetadata: testMetadata,
	}
	if len(req.Errors) > 0 {
		testResult.Verdict = &api.TestCaseResult_Fail_{Fail: &api.TestCaseResult_Fail{}}
		var reasons []string
		for _, e := range req.Errors {
			reasons = append(reasons, e.Reason)
		}
		testResult.Reason = strings.Join(reasons, "\n")
	} else if req.SkipReason != "" {
		testResult.Verdict = &api.TestCaseResult_Skip_{Skip: &api.TestCaseResult_Skip{}}
		testResult.Reason = req.SkipReason
	}
	s.mu.Lock()

	// Check the reported tests (which uses req.Test), to see if a result for the test has previously been reported.
	if _, ok := s.reportedTests[req.Test]; ok {
		// If it has, we will remove the duplicate result, in order to stub in the new proper retry result.
		// testID is used for matching there... a bit odd...
		for i, res := range s.testCaseResults {
			if res.TestCaseId.Value == testID {
				s.testCaseResults = append(s.testCaseResults[:i], s.testCaseResults[i+1:]...)
				break
			}
		}
	}

	// Note, must be created AFTER the dup check; otherwise everything will be a dup
	s.reportedTests[req.Test] = struct{}{}
	s.testCaseResults = append(s.testCaseResults, &testResult)
	s.mu.Unlock()

	return &protocol.ReportResultResponse{}, nil
}

// MissingTestsReports return error results to all tests that have not reported results.
func (s *ReportsServer) MissingTestsReports(reason string) []*api.TestCaseResult {
	var missingTestResults []*api.TestCaseResult
	s.mu.Lock()
	defer s.mu.Unlock()
	if reason == "" {
		reason = "Test did not run"
	}
	for _, t := range s.tests {
		if _, ok := s.reportedTests[t]; ok {
			continue
		}
		testID, ok := s.testNamesToIds[t]
		if !ok {
			continue
		}
		// We still should be able to map the missing tests' metadata.
		testMetadata, ok := s.testNamesToMetadata[t]
		if !ok {
			testMetadata = nil
			s.allErrors = append(s.allErrors, errors.NewStatusError(errors.MissingArgument,
				fmt.Errorf("failed to find test metadata for missing test %v", t)))
		}
		missingTestResults = append(missingTestResults, &api.TestCaseResult{
			TestCaseId: &api.TestCase_Id{Value: testID},
			Verdict:    &api.TestCaseResult_NotRun_{NotRun: &api.TestCaseResult_NotRun{}},
			Reason:     reason,
			TestHarness: &api.TestHarness{
				TestHarnessType: &api.TestHarness_Tast_{
					Tast: &api.TestHarness_Tast{},
				},
			},
			TestCaseMetadata: testMetadata,
		})
	}
	return missingTestResults
}

// TestsReports returns results to all tests that have reported results.
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
func NewReportsServer(port int, tests []string, testNamesToIds map[string]string, testNamesToMetadata map[string]*api.TestCaseMetadata, resultDir string) (*ReportsServer, error) {
	l, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
	if err != nil {
		return nil, err
	}
	s := ReportsServer{
		srv:                 grpc.NewServer(),
		listenerAddr:        l.Addr(),
		reportedTests:       make(map[string]struct{}),
		tests:               tests,
		testResultsDir:      resultDir,
		testNamesToIds:      testNamesToIds,
		testNamesToMetadata: testNamesToMetadata,
	}

	protocol.RegisterReportsServer(s.srv, &s)
	go s.srv.Serve(l)
	return &s, nil
}
