// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testplan_test

import (
	"testing"

	"github.com/google/go-cmp/cmp"
	"github.com/google/go-cmp/cmp/cmpopts"
	configpb "go.chromium.org/chromiumos/config/go/api"
	"go.chromium.org/chromiumos/config/go/api/software"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/payload"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/chromiumos/config/go/test/plan"

	testplan "chromiumos/test/plan/internal"
)

// buildMetadata is a convenience to reduce boilerplate when creating
// SystemImage_BuildMetadata in test cases.
func buildMetadata(overlay, kernelVersion, chipsetOverlay, arcVersion string) *buildpb.SystemImage_BuildMetadata {
	return &buildpb.SystemImage_BuildMetadata{
		BuildTarget: &buildpb.SystemImage_BuildTarget{
			PortageBuildTarget: &buildpb.Portage_BuildTarget{
				OverlayName: overlay,
			},
		},
		PackageSummary: &buildpb.SystemImage_BuildMetadata_PackageSummary{
			Kernel: &buildpb.SystemImage_BuildMetadata_Kernel{
				Version: kernelVersion,
			},
			Chipset: &buildpb.SystemImage_BuildMetadata_Chipset{
				Overlay: chipsetOverlay,
			},
			Arc: &buildpb.SystemImage_BuildMetadata_Arc{
				Version: arcVersion,
			},
		},
	}
}

// flatConfig is a convenience to reduce boilerplate when creating FlatConfig
// in test cases.
func flatConfig(program, design, designConfig string, firmwareROVersion *buildpb.Version) *payload.FlatConfig {
	return &payload.FlatConfig{
		Program:        &configpb.Program{Id: &configpb.ProgramId{Value: program}},
		HwDesign:       &configpb.Design{Id: &configpb.DesignId{Value: design}},
		HwDesignConfig: &configpb.Design_Config{Id: &configpb.DesignConfigId{Value: designConfig}},
		SwConfig: &software.SoftwareConfig{
			Firmware: &buildpb.FirmwareConfig{
				MainRoPayload: &buildpb.FirmwarePayload{
					Version: firmwareROVersion,
				},
			},
		},
	}
}

var buildMetadataList = &buildpb.SystemImage_BuildMetadataList{
	Values: []*buildpb.SystemImage_BuildMetadata{
		buildMetadata("project1", "4.14", "chipsetA", "P"),
		buildMetadata("project2", "4.14", "chipsetB", "R"),
		buildMetadata("project3", "5.4", "chipsetA", ""),
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

var flatConfigList = &payload.FlatConfigList{
	Values: []*payload.FlatConfig{
		flatConfig("ProgA", "Design1", "Config1", &buildpb.Version{Major: 123, Minor: 4, Patch: 5}),
		flatConfig("ProgA", "Design1", "Config2", &buildpb.Version{Major: 123, Minor: 4, Patch: 5}),
		flatConfig("ProgA", "Design2", "Config1", &buildpb.Version{Major: 123, Minor: 0, Patch: 0}),
		flatConfig("ProgB", "Design20", "Config1", &buildpb.Version{Major: 123, Minor: 4, Patch: 0}),
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

	rules, err := testplan.Generate(sourceTestPlans, buildMetadataList, dutAttributeList, flatConfigList)

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
		name              string
		sourceTestPlans   []*plan.SourceTestPlan
		buildMetadataList *buildpb.SystemImage_BuildMetadataList
		dutAttributeList  *testpb.DutAttributeList
	}{
		{
			name:              "empty sourceTestPlans",
			sourceTestPlans:   []*plan.SourceTestPlan{},
			buildMetadataList: buildMetadataList,
			dutAttributeList:  dutAttributeList,
		},
		{
			name: "nil buildMetadataList",
			sourceTestPlans: []*plan.SourceTestPlan{
				{
					Requirements: &plan.SourceTestPlan_Requirements{
						KernelVersions: &plan.SourceTestPlan_Requirements_KernelVersions{},
					},
				},
			},
			buildMetadataList: nil,
			dutAttributeList:  dutAttributeList,
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
			buildMetadataList: buildMetadataList,
			dutAttributeList:  nil,
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
			buildMetadataList: buildMetadataList,
			dutAttributeList:  dutAttributeList,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if _, err := testplan.Generate(
				test.sourceTestPlans, test.buildMetadataList, test.dutAttributeList, flatConfigList,
			); err == nil {
				t.Error("Expected error from Generate")
			}
		})
	}
}
