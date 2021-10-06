// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package driver implements test drivers for Tast and Autotest tests.
package driver

import (
	"context"

	"go.chromium.org/chromiumos/config/go/test/api"
)

// Helper function that creates a quick lookup to get test Id by test name
func getTestNamesToIds(tests []*api.TestCaseMetadata) map[string]string {
	testNamesToIds := make(map[string]string)
	for _, tc := range tests {
		testNamesToIds[tc.TestCase.Name] = tc.TestCase.Id.Value
	}

	return testNamesToIds
}

// Helper function to get list of test names from TestCaseMetadata array
func getTestNames(tests []*api.TestCaseMetadata) []string {
	testNames := []string{}
	for _, tc := range tests {
		testNames = append(testNames, tc.TestCase.Name)
	}

	return testNames
}

// Driver provides common interface to execute Tast and Autotest.
type Driver interface {
	// RunTests drives a test framework to execute tests.
	RunTests(ctx context.Context, resultsDir, dut, tlwAddr string, tests []*api.TestCaseMetadata) (*api.RunTestsResponse, error)

	// Name returns the name of the driver.
	Name() string
}
