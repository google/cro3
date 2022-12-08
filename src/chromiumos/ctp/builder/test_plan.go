// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package builder

import (
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
)

// TestPlanFor Tests constructs a Test Platform test plan for the given tests.
// testArgs meanings depend on tests
func TestPlanForTests(testArgs string, testHarness string, testNames []string) *test_platform.Request_TestPlan {
	// Due to crbug/984103, the first autotest arg gets dropped somewhere between here and
	// when autotest reads the args. Add a dummy arg to prevent this bug for now.
	// TODO(crbug/984103): Remove the dummy arg once the underlying bug is fixed.
	if testArgs != "" {
		testArgs = "dummy=crbug/984103 " + testArgs
	}
	testPlan := &test_platform.Request_TestPlan{}
	for _, testName := range testNames {
		if testHarness != "" {
			testName = testHarness + "." + testName
		}
		testRequest := &test_platform.Request_Test{
			Harness: &test_platform.Request_Test_Autotest_{
				Autotest: &test_platform.Request_Test_Autotest{
					Name:     testName,
					TestArgs: testArgs,
				},
			},
		}
		testPlan.Test = append(testPlan.Test, testRequest)
	}
	return testPlan
}

// TestPlanForSuites constructs a Test Platform test plan for the given suites.
func TestPlanForSuites(suiteNames []string) *test_platform.Request_TestPlan {
	testPlan := test_platform.Request_TestPlan{}
	for _, suiteName := range suiteNames {
		suiteRequest := &test_platform.Request_Suite{Name: suiteName}
		testPlan.Suite = append(testPlan.Suite, suiteRequest)
	}
	return &testPlan
}
