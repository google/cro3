// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package coveragerules_test

import (
	"chromiumos/test/plan/internal/coveragerules"
	"testing"

	"github.com/google/go-cmp/cmp"
	"github.com/google/go-cmp/cmp/cmpopts"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/chromiumos/config/go/test/plan"
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
		buildSummary("project1", "4.14", "chipsetA", ""),
		buildSummary("project2", "4.14", "chipsetB", ""),
		buildSummary("project3", "5.4", "chipsetA", ""),
		buildSummary("project4", "3.18", "chipsetC", "R"),
		buildSummary("project5", "4.14", "chipsetA", ""),
		buildSummary("project6", "4.14", "chipsetB", "P"),
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
	tests := []struct {
		name     string
		input    *plan.SourceTestPlan
		expected []*testpb.CoverageRule
	}{
		{
			name: "kernel versions",
			input: &plan.SourceTestPlan{
				Requirements: &plan.SourceTestPlan_Requirements{
					KernelVersions: &plan.SourceTestPlan_Requirements_KernelVersions{},
				},
				TestTags:        []string{"kernel"},
				TestTagExcludes: []string{"flaky"},
			},
			expected: []*testpb.CoverageRule{
				{
					Name: "kernel:3.18",
					DutCriteria: []*testpb.DutCriterion{
						{
							AttributeId: &testpb.DutAttribute_Id{
								Value: "system_build_target",
							},
							Values: []string{"project4"},
						},
					},
					TestSuites: []*testpb.TestSuite{
						{
							TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
								Tags:        []string{"kernel"},
								TagExcludes: []string{"flaky"},
							},
						},
					},
				},
				{
					Name: "kernel:4.14",
					DutCriteria: []*testpb.DutCriterion{
						{
							AttributeId: &testpb.DutAttribute_Id{
								Value: "system_build_target",
							},
							Values: []string{"project1", "project2", "project5", "project6"},
						},
					},
					TestSuites: []*testpb.TestSuite{
						{
							TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
								Tags:        []string{"kernel"},
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
								Tags:        []string{"kernel"},
								TagExcludes: []string{"flaky"},
							},
						},
					},
				},
			},
		},
		{
			name: "soc families",
			input: &plan.SourceTestPlan{
				Requirements: &plan.SourceTestPlan_Requirements{
					SocFamilies: &plan.SourceTestPlan_Requirements_SocFamilies{},
				},
				TestTagExcludes: []string{"flaky"},
			},
			expected: []*testpb.CoverageRule{
				{
					Name: "soc:chipsetA",
					DutCriteria: []*testpb.DutCriterion{
						{
							AttributeId: &testpb.DutAttribute_Id{
								Value: "system_build_target",
							},
							Values: []string{"project1", "project3", "project5"},
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
					Name: "soc:chipsetB",
					DutCriteria: []*testpb.DutCriterion{
						{
							AttributeId: &testpb.DutAttribute_Id{
								Value: "system_build_target",
							},
							Values: []string{"project2", "project6"},
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
					Name: "soc:chipsetC",
					DutCriteria: []*testpb.DutCriterion{
						{
							AttributeId: &testpb.DutAttribute_Id{
								Value: "system_build_target",
							},
							Values: []string{"project4"},
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
			},
		},
		{
			name: "build targets and designs",
			input: &plan.SourceTestPlan{
				Requirements: &plan.SourceTestPlan_Requirements{
					KernelVersions: &plan.SourceTestPlan_Requirements_KernelVersions{},
					Fingerprint:    &plan.SourceTestPlan_Requirements_Fingerprint{},
				},
				TestTags: []string{"kernel", "fingerprint"},
			},
			expected: []*testpb.CoverageRule{
				{
					Name: "fp:present",
					DutCriteria: []*testpb.DutCriterion{
						{
							AttributeId: &testpb.DutAttribute_Id{
								Value: "fingerprint_location",
							},
							Values: []string{
								"POWER_BUTTON_TOP_LEFT",
								"KEYBOARD_BOTTOM_LEFT",
								"KEYBOARD_BOTTOM_RIGHT",
								"KEYBOARD_TOP_RIGHT",
								"RIGHT_SIDE",
								"LEFT_SIDE",
								"PRESENT",
							},
						},
					},
					TestSuites: []*testpb.TestSuite{
						{
							TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
								Tags: []string{"kernel", "fingerprint"},
							},
						},
					},
				},
				{
					Name: "kernel:3.18",
					DutCriteria: []*testpb.DutCriterion{
						{
							AttributeId: &testpb.DutAttribute_Id{
								Value: "system_build_target",
							},
							Values: []string{"project4"},
						},
					},
					TestSuites: []*testpb.TestSuite{
						{
							TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
								Tags: []string{"kernel", "fingerprint"},
							},
						},
					},
				},
				{
					Name: "kernel:4.14",
					DutCriteria: []*testpb.DutCriterion{
						{
							AttributeId: &testpb.DutAttribute_Id{
								Value: "system_build_target",
							},
							Values: []string{"project1", "project2", "project5", "project6"},
						},
					},
					TestSuites: []*testpb.TestSuite{
						{
							TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
								Tags: []string{"kernel", "fingerprint"},
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
								Tags: []string{"kernel", "fingerprint"},
							},
						},
					},
				},
			},
		},
		{
			name: "multiple requirements",
			input: &plan.SourceTestPlan{
				Requirements: &plan.SourceTestPlan_Requirements{
					KernelVersions: &plan.SourceTestPlan_Requirements_KernelVersions{},
					SocFamilies:    &plan.SourceTestPlan_Requirements_SocFamilies{},
					ArcVersions:    &plan.SourceTestPlan_Requirements_ArcVersions{},
				},
				TestTags: []string{"kernel", "arc"},
			},
			expected: []*testpb.CoverageRule{
				{
					Name: "kernel:4.14_soc:chipsetA",
					DutCriteria: []*testpb.DutCriterion{
						{
							AttributeId: &testpb.DutAttribute_Id{
								Value: "system_build_target",
							},
							Values: []string{"project1", "project5"},
						},
					},
					TestSuites: []*testpb.TestSuite{
						{
							TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
								Tags: []string{"kernel", "arc"},
							},
						},
					},
				},
				{
					Name: "kernel:4.14_soc:chipsetB_arc:P",
					DutCriteria: []*testpb.DutCriterion{
						{
							AttributeId: &testpb.DutAttribute_Id{
								Value: "system_build_target",
							},
							Values: []string{"project6"},
						},
					},
					TestSuites: []*testpb.TestSuite{
						{
							TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
								Tags: []string{"kernel", "arc"},
							},
						},
					},
				},
				{
					Name: "kernel:5.4_soc:chipsetA",
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
								Tags: []string{"kernel", "arc"},
							},
						},
					},
				},
				{
					Name: "kernel:3.18_soc:chipsetC_arc:R",
					DutCriteria: []*testpb.DutCriterion{
						{
							AttributeId: &testpb.DutAttribute_Id{
								Value: "system_build_target",
							},
							Values: []string{"project4"},
						},
					},
					TestSuites: []*testpb.TestSuite{
						{
							TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
								Tags: []string{"kernel", "arc"},
							},
						},
					},
				},
			},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			outputs, err := coveragerules.Generate(test.input, buildSummaryList, dutAttributeList)
			if err != nil {
				t.Fatalf("coveragerules.Generate failed: %s", err)
			}
			if diff := cmp.Diff(
				test.expected,
				outputs,
				cmpopts.SortSlices(func(i, j *testpb.CoverageRule) bool {
					return i.Name < j.Name
				}),
				cmpopts.SortSlices(func(i, j string) bool {
					return i < j
				}),
			); diff != "" {
				t.Errorf("coveragerules.Generate returned unexpected diff (-want +got):\n%s", diff)
			}
		})
	}
}
func TestGenerateErrors(t *testing.T) {
	tests := []struct {
		name             string
		input            *plan.SourceTestPlan
		dutAttributeList *testpb.DutAttributeList
	}{
		{
			name: "no requirements",
			input: &plan.SourceTestPlan{
				EnabledTestEnvironments: []plan.SourceTestPlan_TestEnvironment{
					plan.SourceTestPlan_HARDWARE,
				},
			},
			dutAttributeList: dutAttributeList,
		},
		{
			name: "invalid dut attributes",
			input: &plan.SourceTestPlan{
				EnabledTestEnvironments: []plan.SourceTestPlan_TestEnvironment{
					plan.SourceTestPlan_HARDWARE,
				},
				Requirements: &plan.SourceTestPlan_Requirements{
					KernelVersions: &plan.SourceTestPlan_Requirements_KernelVersions{},
				},
			},
			dutAttributeList: &testpb.DutAttributeList{
				DutAttributes: []*testpb.DutAttribute{
					{
						Id: &testpb.DutAttribute_Id{
							Value: "miscdutattr",
						},
						FieldPath: "a.b.c",
					},
				},
			},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if _, err := coveragerules.Generate(
				test.input, buildSummaryList, test.dutAttributeList,
			); err == nil {
				t.Errorf("Expected error from coveragerules.Generate")
			}
		})
	}
}
