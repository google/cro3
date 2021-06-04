// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package merge_test

import (
	"chromiumos/test/plan/internal/merge"
	"testing"

	"github.com/google/go-cmp/cmp"
	"github.com/google/go-cmp/cmp/cmpopts"
	"go.chromium.org/chromiumos/config/go/test/plan"
)

func TestSourceTestPlans(t *testing.T) {
	tests := []struct {
		name     string
		input    []*plan.SourceTestPlan
		expected *plan.SourceTestPlan
	}{
		{
			name: "basic",
			input: []*plan.SourceTestPlan{
				{
					EnabledTestEnvironments: []plan.SourceTestPlan_TestEnvironment{
						plan.SourceTestPlan_HARDWARE,
					},
					PathRegexps:        []string{`a/b/.*\.c`},
					PathRegexpExcludes: []string{`.*\.md`},
					Requirements: &plan.SourceTestPlan_Requirements{
						KernelVersions: &plan.SourceTestPlan_Requirements_KernelVersions{},
					}},
				{
					EnabledTestEnvironments: []plan.SourceTestPlan_TestEnvironment{
						plan.SourceTestPlan_HARDWARE,
					},
					TestTags:        []string{"componentA", "componentB"},
					TestTagExcludes: []string{"componentC", "flaky"},
					Requirements: &plan.SourceTestPlan_Requirements{
						KernelVersions: &plan.SourceTestPlan_Requirements_KernelVersions{},
					},
				},
				{
					EnabledTestEnvironments: []plan.SourceTestPlan_TestEnvironment{
						plan.SourceTestPlan_VIRTUAL,
					},
					TestTags:           []string{"componentC"},
					TestTagExcludes:    []string{"flaky"},
					PathRegexpExcludes: []string{`.*README`},
					Requirements: &plan.SourceTestPlan_Requirements{
						SocFamilies: &plan.SourceTestPlan_Requirements_SocFamilies{},
					},
				},
			},
			expected: &plan.SourceTestPlan{
				EnabledTestEnvironments: []plan.SourceTestPlan_TestEnvironment{
					plan.SourceTestPlan_HARDWARE,
					plan.SourceTestPlan_VIRTUAL,
				},
				TestTags:        []string{"componentA", "componentB", "componentC"},
				TestTagExcludes: []string{"flaky"},
				Requirements: &plan.SourceTestPlan_Requirements{
					KernelVersions: &plan.SourceTestPlan_Requirements_KernelVersions{},
					SocFamilies:    &plan.SourceTestPlan_Requirements_SocFamilies{},
				},
			},
		},
		{
			name: "single plan",
			input: []*plan.SourceTestPlan{
				{
					EnabledTestEnvironments: []plan.SourceTestPlan_TestEnvironment{
						plan.SourceTestPlan_VIRTUAL,
					},
					TestTags:           []string{"componentC"},
					TestTagExcludes:    []string{"flaky"},
					PathRegexpExcludes: []string{`.*README`},
					Requirements: &plan.SourceTestPlan_Requirements{
						SocFamilies: &plan.SourceTestPlan_Requirements_SocFamilies{},
					},
				},
			},
			expected: &plan.SourceTestPlan{
				EnabledTestEnvironments: []plan.SourceTestPlan_TestEnvironment{
					plan.SourceTestPlan_VIRTUAL,
				},
				TestTags:        []string{"componentC"},
				TestTagExcludes: []string{"flaky"},
				Requirements: &plan.SourceTestPlan_Requirements{
					SocFamilies: &plan.SourceTestPlan_Requirements_SocFamilies{},
				},
			},
		},
		{
			name:     "no plans",
			input:    []*plan.SourceTestPlan{},
			expected: &plan.SourceTestPlan{},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			merged := merge.SourceTestPlans(test.input...)
			if diff := cmp.Diff(
				test.expected,
				merged,
				cmpopts.EquateEmpty(),
				cmpopts.SortSlices(func(x, y string) bool {
					return x < y
				}),
				// protocmp.Transform(),
				// protocmp.SortRepeated(func(x, y string) bool {
				// 	return x < y
				// }),
			); diff != "" {
				t.Errorf(
					"mergeSourceTestPlans(%v) returned unexpected diff (-want +got):\n%s",
					test.input, diff,
				)
			}
		})
	}
}
