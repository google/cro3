// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testplan_test

import (
	"context"
	"io/ioutil"
	"os"
	"path"
	"testing"

	"github.com/google/go-cmp/cmp"
	configpb "go.chromium.org/chromiumos/config/go/api"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/payload"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	test_api_v1 "go.chromium.org/chromiumos/config/go/test/api/v1"
	"google.golang.org/protobuf/testing/protocmp"

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
			Id: &testpb.DutAttribute_Id{Value: "fingerprint_location"},
			DataSource: &testpb.DutAttribute_FlatConfigSource_{
				FlatConfigSource: &testpb.DutAttribute_FlatConfigSource{
					Fields: []*testpb.DutAttribute_FieldSpec{
						{
							Path: "design_list.configs.hardware_features.fingerprint.location",
						},
					},
				},
			},
		},
		{
			Id: &testpb.DutAttribute_Id{Value: "system_build_target"},
			DataSource: &testpb.DutAttribute_FlatConfigSource_{
				FlatConfigSource: &testpb.DutAttribute_FlatConfigSource{
					Fields: []*testpb.DutAttribute_FieldSpec{
						{
							Path: "software_configs.system_build_target.portage_build_target.overlay_name",
						},
					},
				},
			},
		},
	},
}

var configBundleList = &payload.ConfigBundleList{
	Values: []*payload.ConfigBundle{
		{
			ProgramList: []*configpb.Program{
				{
					Id: &configpb.ProgramId{
						Value: "ProgA",
					},
				},
			},
		},
		{
			ProgramList: []*configpb.Program{
				{
					Id: &configpb.ProgramId{
						Value: "ProgB",
					},
				},
			},
		},
		{
			DesignList: []*configpb.Design{
				{
					Id: &configpb.DesignId{
						Value: "Design1",
					},
				},
				{
					Id: &configpb.DesignId{
						Value: "Design2",
					},
				},
			},
		},
	},
}

// writeTempStarlarkFile writes starlarkSource to a temp file created under
// a t.TempDir().
func writeTempStarlarkFile(t *testing.T, starlarkSource string) string {
	testDir := t.TempDir()
	planFilename := path.Join(testDir, "test.star")

	if err := ioutil.WriteFile(
		planFilename,
		[]byte(starlarkSource),
		os.ModePerm,
	); err != nil {
		t.Fatal(err)
	}

	return planFilename
}

func TestGenerate(t *testing.T) {
	ctx := context.Background()

	starlarkSource := `
load("@proto//chromiumos/test/api/v1/plan.proto", plan_pb = "chromiumos.test.api.v1")

build_metadata = testplan.get_build_metadata()
config_bundles = testplan.get_config_bundle_list()
print('Got {} BuildMetadatas'.format(len(build_metadata.values)))
print('Got {} ConfigBundles'.format(len(config_bundles.values)))
testplan.add_hw_test_plan(
	plan_pb.HWTestPlan(id=plan_pb.HWTestPlan.TestPlanId(value='plan1'))
)
	`

	planFilename := writeTempStarlarkFile(
		t, starlarkSource,
	)

	testPlans, err := testplan.Generate(
		ctx, []string{planFilename}, buildMetadataList, dutAttributeList, configBundleList,
	)
	if err != nil {
		t.Fatal(err)
	}

	expectedTestPlans := []*test_api_v1.HWTestPlan{
		{Id: &test_api_v1.HWTestPlan_TestPlanId{Value: "plan1"}},
	}

	if len(expectedTestPlans) != len(testPlans) {
		t.Errorf("expected %d test plans, got %d", len(expectedTestPlans), len(testPlans))
	}

	for i, expected := range expectedTestPlans {
		if diff := cmp.Diff(expected, testPlans[i], protocmp.Transform()); diff != "" {
			t.Errorf("returned unexpected diff in test plan %d (-want +got):\n%s", i, diff)
		}
	}
}

func TestGenerateErrors(t *testing.T) {
	ctx := context.Background()

	tests := []struct {
		name              string
		planFilenames     []string
		buildMetadataList *buildpb.SystemImage_BuildMetadataList
		dutAttributeList  *testpb.DutAttributeList
		configBundleList  *payload.ConfigBundleList
	}{
		{
			name:              "empty planFilenames",
			planFilenames:     []string{},
			buildMetadataList: buildMetadataList,
			dutAttributeList:  dutAttributeList,
			configBundleList:  configBundleList,
		},
		{
			name:              "nil buildMetadataList",
			planFilenames:     []string{"plan1.star"},
			buildMetadataList: nil,
			dutAttributeList:  dutAttributeList,
			configBundleList:  configBundleList,
		},
		{
			name:              "nil dutAttributeList",
			planFilenames:     []string{"plan1.star"},
			buildMetadataList: buildMetadataList,
			dutAttributeList:  nil,
			configBundleList:  configBundleList,
		},
		{
			name:              "nil ConfigBundleList",
			planFilenames:     []string{"plan1.star"},
			buildMetadataList: buildMetadataList,
			dutAttributeList:  dutAttributeList,
			configBundleList:  nil,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if _, err := testplan.Generate(
				ctx, test.planFilenames, test.buildMetadataList, test.dutAttributeList, test.configBundleList,
			); err == nil {
				t.Error("Expected error from Generate")
			}
		})
	}
}
