// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the executionservice server
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/chromiumos/config/go/test/api"

	"chromiumos/test/execution/cmd/testexecserver/internal/driver"
	statuserrors "chromiumos/test/execution/errors"
)

// driverToTestsMapping builds a map between test and its driver.
func driverToTestsMapping(logger *log.Logger, tests []string, mdList *api.TestCaseMetadataList) (map[driver.Driver][]string, error) {
	tastDriver := driver.NewTastDriver(logger)
	tautoDriver := driver.NewTautoDriver(logger)
	driverToTests := make(map[driver.Driver][]string)
	unvisited := make(map[string]struct{})
	for _, t := range tests {
		unvisited[t] = struct{}{}
	}
	for _, md := range mdList.Values {
		if md.TestCase == nil {
			return nil, statuserrors.NewStatusError(statuserrors.InvalidArgument,
				fmt.Errorf("missing test case information %v", md))
		}
		if md.TestCaseExec == nil || md.TestCaseExec.TestHarness == nil {
			return nil, statuserrors.NewStatusError(statuserrors.InvalidArgument,
				fmt.Errorf("test case %v does not have test harness information", md.TestCase.Name))
		}
		_, ok := unvisited[md.TestCase.Name]
		if !ok {
			// Only process tests that users intent to run.
			continue
		}
		delete(unvisited, md.TestCase.Name)
		if md.TestCaseExec.TestHarness.GetTast() != nil {
			driverToTests[tastDriver] = append(driverToTests[tastDriver], md.TestCase.Name)
		} else if md.TestCaseExec.TestHarness.GetTauto() != nil {
			driverToTests[tautoDriver] = append(driverToTests[tautoDriver], md.TestCase.Name)
		} else {
			return nil, statuserrors.NewStatusError(statuserrors.InvalidArgument,
				errors.New("manual harness has not been supported"))
		}
	}
	if len(unvisited) > 0 {
		unvisitedTests := []string{}
		for t := range unvisited {
			unvisitedTests = append(unvisitedTests, t)
		}
		return nil, statuserrors.NewStatusError(statuserrors.InvalidArgument,
			fmt.Errorf("following tests have no metadata, %v", unvisitedTests))
	}
	return driverToTests, nil
}

func getTests(req *api.RunTestsRequest) []string {
	var tests []string
	for _, suite := range req.TestSuites {
		if suite.TestCaseIds == nil {
			continue
		}
		for _, tc := range suite.TestCaseIds.TestCaseIds {
			tests = append(tests, tc.Value)
		}
		// TO-DO Support Tags
	}
	return tests
}

// runTests runs the requested tests.
func runTests(ctx context.Context, logger *log.Logger, tlwAddr string, metadataList *api.TestCaseMetadataList, req *api.RunTestsRequest) (*api.RunTestsResponse, error) {
	driversToTests, err := driverToTestsMapping(logger, getTests(req), metadataList)
	if err != nil {
		return nil, err
	}
	allRspn := api.RunTestsResponse{}

	for driver, tests := range driversToTests {
		rspn, err := driver.RunTests(ctx, "", req.Dut.PrimaryHost, tlwAddr, tests)
		if err != nil {
			return nil, err
		}
		allRspn.TestCaseResults = append(allRspn.TestCaseResults, rspn.TestCaseResults...)
	}
	return &allRspn, nil
}

// readInput reads an execution_service json file and returns a pointer to RunTestsRequest.
func readInput(fileName string) (*api.RunTestsRequest, error) {
	f, err := os.Open(fileName)
	if err != nil {
		return nil, statuserrors.NewStatusError(statuserrors.IOAccessError,
			fmt.Errorf("fail to read file %v: %v", fileName, err))
	}
	req := api.RunTestsRequest{}
	if err := jsonpb.Unmarshal(f, &req); err != nil {
		return nil, statuserrors.NewStatusError(statuserrors.UnmarshalError,
			fmt.Errorf("fail to unmarshal file %v: %v", fileName, err))
	}
	return &req, nil
}

// writeOutput writes a RunTestsResponse json.
func writeOutput(output string, resp *api.RunTestsResponse) error {
	f, err := os.Create(output)
	if err != nil {
		return statuserrors.NewStatusError(statuserrors.IOCreateError,
			fmt.Errorf("fail to create file %v: %v", output, err))
	}
	m := jsonpb.Marshaler{}
	if err := m.Marshal(f, resp); err != nil {
		return statuserrors.NewStatusError(statuserrors.MarshalError,
			fmt.Errorf("failed to marshall response to file %v: %v", output, err))
	}
	return nil
}
