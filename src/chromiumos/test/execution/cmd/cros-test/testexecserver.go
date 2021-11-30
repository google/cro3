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
	"path/filepath"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/chromiumos/config/go/test/api"

	"chromiumos/test/execution/cmd/cros-test/internal/driver"
	statuserrors "chromiumos/test/execution/errors"
	"chromiumos/test/util/finder"
)

// driverToTestsMapping builds a map between test and its driver.
func driverToTestsMapping(logger *log.Logger, mdList []*api.TestCaseMetadata) (map[driver.Driver][]*api.TestCaseMetadata, error) {
	tastDriver := driver.NewTastDriver(logger)
	tautoDriver := driver.NewTautoDriver(logger)
	gtestDriver := driver.NewGtestDriver(logger)

	driverToTests := make(map[driver.Driver][]*api.TestCaseMetadata)
	for _, md := range mdList {
		if md.TestCase == nil {
			return nil, statuserrors.NewStatusError(statuserrors.InvalidArgument,
				fmt.Errorf("missing test case information %v", md))
		}
		if md.TestCaseExec == nil || md.TestCaseExec.TestHarness == nil {
			return nil, statuserrors.NewStatusError(statuserrors.InvalidArgument,
				fmt.Errorf("test case %v does not have test harness information", md.TestCase.Name))
		}

		if md.TestCaseExec.TestHarness.GetTast() != nil {
			driverToTests[tastDriver] = append(driverToTests[tastDriver], md)
		} else if md.TestCaseExec.TestHarness.GetTauto() != nil {
			driverToTests[tautoDriver] = append(driverToTests[tautoDriver], md)
		} else if md.TestCaseExec.TestHarness.GetGtest() != nil {
			driverToTests[gtestDriver] = append(driverToTests[gtestDriver], md)
		} else {
			return nil, statuserrors.NewStatusError(statuserrors.InvalidArgument,
				errors.New("manual harness has not been supported"))
		}
	}
	return driverToTests, nil
}

// runTests runs the requested tests.
func runTests(ctx context.Context, logger *log.Logger, resultRootDir, tlwAddr string, metadataList *api.TestCaseMetadataList, req *api.CrosTestRequest) (*api.CrosTestResponse, error) {
	matchedMdList, err := finder.MatchedTestsForSuites(metadataList.Values, req.TestSuites)
	if err != nil {
		return nil, statuserrors.NewStatusError(statuserrors.InvalidArgument,
			fmt.Errorf("failed to match test metadata: %v", err))
	}

	driversToTests, err := driverToTestsMapping(logger, matchedMdList)
	if err != nil {
		return nil, err
	}
	allRspn := api.CrosTestResponse{}

	for driver, tests := range driversToTests {
		resultsDir := filepath.Join(resultRootDir, driver.Name())
		// Make sure the result directory exists.
		if err := os.MkdirAll(resultsDir, 0755); err != nil {
			return nil, statuserrors.NewStatusError(statuserrors.IOCreateError,
				fmt.Errorf("failed to create result directory %v", resultsDir))
		}
		rspn, err := driver.RunTests(ctx, resultsDir, req, tlwAddr, tests)
		if err != nil {
			return nil, err
		}
		allRspn.TestCaseResults = append(allRspn.TestCaseResults, rspn.TestCaseResults...)
	}
	return &allRspn, nil
}

// readInput reads an execution_service json file and returns a pointer to RunTestsRequest.
func readInput(fileName string) (*api.CrosTestRequest, error) {
	f, err := os.Open(fileName)
	if err != nil {
		return nil, statuserrors.NewStatusError(statuserrors.IOAccessError,
			fmt.Errorf("fail to read file %v: %v", fileName, err))
	}
	req := api.CrosTestRequest{}
	if err := jsonpb.Unmarshal(f, &req); err != nil {
		return nil, statuserrors.NewStatusError(statuserrors.UnmarshalError,
			fmt.Errorf("fail to unmarshal file %v: %v", fileName, err))
	}
	return &req, nil
}

// writeOutput writes a RunTestsResponse json.
func writeOutput(output string, resp *api.CrosTestResponse) error {
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
