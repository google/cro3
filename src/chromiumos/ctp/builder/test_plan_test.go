// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package builder

import (
	"fmt"
	"testing"

	"github.com/google/go-cmp/cmp"
	"github.com/google/go-cmp/cmp/cmpopts"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
)

type TestTestPlanForTestsInput struct {
	testArgs    string
	testHarness string
	testNames   []string
}

var testTestPlanForTestsData = []struct {
	testName string
	input    TestTestPlanForTestsInput
	want     *test_platform.Request_TestPlan
}{
	{
		"with harness",
		TestTestPlanForTestsInput{
			testArgs:    "foo=bar",
			testHarness: "test-harness",
			testNames:   []string{"eli", "cool"},
		},
		&test_platform.Request_TestPlan{
			Test: []*test_platform.Request_Test{
				{
					Harness: &test_platform.Request_Test_Autotest_{
						Autotest: &test_platform.Request_Test_Autotest{
							Name:     "test-harness.eli",
							TestArgs: "dummy=crbug/984103 foo=bar",
						},
					},
				},
				{
					Harness: &test_platform.Request_Test_Autotest_{
						Autotest: &test_platform.Request_Test_Autotest{
							Name:     "test-harness.cool",
							TestArgs: "dummy=crbug/984103 foo=bar",
						},
					},
				},
			},
		},
	},
	{
		"without harness",
		TestTestPlanForTestsInput{
			testArgs:  "foo=bar",
			testNames: []string{"eli", "cool"},
		},
		&test_platform.Request_TestPlan{
			Test: []*test_platform.Request_Test{
				{
					Harness: &test_platform.Request_Test_Autotest_{
						Autotest: &test_platform.Request_Test_Autotest{
							Name:     "eli",
							TestArgs: "dummy=crbug/984103 foo=bar",
						},
					},
				},
				{
					Harness: &test_platform.Request_Test_Autotest_{
						Autotest: &test_platform.Request_Test_Autotest{
							Name:     "cool",
							TestArgs: "dummy=crbug/984103 foo=bar",
						},
					},
				},
			},
		},
	},
}

func TestTestPlanForTests(t *testing.T) {
	t.Parallel()
	for _, tt := range testTestPlanForTestsData {
		tt := tt
		t.Run(fmt.Sprintf("%v", tt.input), func(t *testing.T) {
			t.Parallel()
			got := TestPlanForTests(tt.input.testArgs, tt.input.testHarness, tt.input.testNames)
			if diff := cmp.Diff(tt.want, got, cmpopts.IgnoreUnexported(test_platform.Request_TestPlan{}, test_platform.Request_Test{}, test_platform.Request_Test_Autotest{})); diff != "" {
				t.Errorf("unexpected diff (%s)", diff)
			}
		})
	}
}

func TestTestPlanForSuites(t *testing.T) {
	t.Parallel()

	got := TestPlanForSuites([]string{"foo", "bar"})
	want := &test_platform.Request_TestPlan{
		Suite: []*test_platform.Request_Suite{
			{
				Name: "foo",
			},
			{
				Name: "bar",
			},
		},
	}

	if diff := cmp.Diff(want, got, cmpopts.IgnoreUnexported(test_platform.Request_TestPlan{}, test_platform.Request_Suite{})); diff != "" {
		t.Errorf("unexpected diff (%s)", diff)
	}
}
