// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testplan_test

import (
	"testing"

	"github.com/google/go-cmp/cmp"
	"github.com/google/go-cmp/cmp/cmpopts"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/chromiumos/config/go/test/plan"

	testplan "chromiumos/test/plan/internal"
)

// buildSummary is a convenience to reduce boilerplate when creating
// SystemImage_BuildSummary in test cases.
func buildSummary(overlay, kernelVersion, chipsetOverlay, arcVersion string) *buildpb.SystemImage_BuildSummary {
	return &buildpb.SystemImage_BuildSummary{
		BuildTarget: &buildpb.SystemImage_BuildTarget{
			PortageBuildTarget: &buildpb.Portage_BuildTarget{
				OverlayName: overlay,
			},
		},
		Kernel: &buildpb.SystemImage_BuildSummary_Kernel{
			Version: kernelVersion,
		},
		Chipset: &buildpb.SystemImage_BuildSummary_Chipset{
			Overlay: chipsetOverlay,
		},
		Arc: &buildpb.SystemImage_BuildSummary_Arc{
			Version: arcVersion,
		},
	}
}

var buildSummaryList = &buildpb.SystemImage_BuildSummaryList{
	Values: []*buildpb.SystemImage_BuildSummary{
		buildSummary("project1", "4.14", "chipsetA", "P"),
		buildSummary("project2", "4.14", "chipsetB", "R"),
		buildSummary("project3", "5.4", "chipsetA", ""),
	},
}

var dutAttributeList = &testpb.DutAttributeList{
	DutAttributes: []*testpb.DutAttribute{
		{
			Id:        &testpb.DutAttribute_Id{Value: "fingerprint_location"},
			FieldPath: "design_list.configs.hardware_features.fingerprint.location",
		},
		{
			Id:        &testpb.DutAttribute_Id{Value: "system_build_target"},
			FieldPath: "software_configs.system_build_target.portage_build_target.overlay_name",
		},
	},
}

func TestGenerate(t *testing.T) {
	sourceTestPlans := []*plan.SourceTestPlan{
		{
			Requirements: &plan.SourceTestPlan_Requirements{
				KernelVersions: &plan.SourceTestPlan_Requirements_KernelVersions{},
			},
			TestTagExcludes: []string{"flaky"},
		},
	}

	rules, err := testplan.Generate(sourceTestPlans, buildSummaryList, dutAttributeList)

	if err != nil {
		t.Fatalf("Generate returned error: %v", err)
	}

	expectedRules := []*testpb.CoverageRule{
		{
			Name: "kernel:4.14",
			DutCriteria: []*testpb.DutCriterion{
				{
					AttributeId: &testpb.DutAttribute_Id{
						Value: "system_build_target",
					},
					Values: []string{"project1", "project2"},
				},
			},
			TestSuites: []*testpb.TestSuite{
				{
					TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
						TagExcludes: []string{"flaky"},
					},
				},
			},
		},
		{
			Name: "kernel:5.4",
			DutCriteria: []*testpb.DutCriterion{
				{
					AttributeId: &testpb.DutAttribute_Id{
						Value: "system_build_target",
					},
					Values: []string{"project3"},
				},
			},
			TestSuites: []*testpb.TestSuite{
				{
					TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
						TagExcludes: []string{"flaky"},
					},
				},
			},
		},
	}

	if diff := cmp.Diff(
		expectedRules,
		rules,
		cmpopts.SortSlices(func(i, j *testpb.CoverageRule) bool {
			return i.Name < j.Name
		}),
		cmpopts.SortSlices(func(i, j string) bool {
			return i < j
		}),
		cmpopts.EquateEmpty(),
	); diff != "" {
		t.Errorf("generate returned unexpected diff (-want +got):\n%s", diff)
	}
}

func TestGenerateErrors(t *testing.T) {
	tests := []struct {
		name             string
		sourceTestPlans  []*plan.SourceTestPlan
		buildSummaryList *buildpb.SystemImage_BuildSummaryList
		dutAttributeList *testpb.DutAttributeList
	}{
		{
			name:             "empty sourceTestPlans",
			sourceTestPlans:  []*plan.SourceTestPlan{},
			buildSummaryList: buildSummaryList,
			dutAttributeList: dutAttributeList,
		},
		{
			name: "nil buildSummaryList",
			sourceTestPlans: []*plan.SourceTestPlan{
				{
					Requirements: &plan.SourceTestPlan_Requirements{
						KernelVersions: &plan.SourceTestPlan_Requirements_KernelVersions{},
					},
				},
			},
			buildSummaryList: nil,
			dutAttributeList: dutAttributeList,
		},
		{
			name: "nil dutAttributeList",
			sourceTestPlans: []*plan.SourceTestPlan{
				{
					Requirements: &plan.SourceTestPlan_Requirements{
						KernelVersions: &plan.SourceTestPlan_Requirements_KernelVersions{},
					},
				},
			},
			buildSummaryList: buildSummaryList,
			dutAttributeList: nil,
		},
		{
			name: "plans has paths set",
			sourceTestPlans: []*plan.SourceTestPlan{
				{
					EnabledTestEnvironments: []plan.SourceTestPlan_TestEnvironment{
						plan.SourceTestPlan_HARDWARE,
					},
					Requirements: &plan.SourceTestPlan_Requirements{
						KernelVersions: &plan.SourceTestPlan_Requirements_KernelVersions{},
					},
					TestTagExcludes: []string{"flaky"},
					PathRegexps:     []string{"a/b/c"},
				},
			},
			buildSummaryList: buildSummaryList,
			dutAttributeList: dutAttributeList,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if _, err := testplan.Generate(test.sourceTestPlans, test.buildSummaryList, test.dutAttributeList); err == nil {
				t.Error("Expected error from Generate")
			}
		})
	}
}
