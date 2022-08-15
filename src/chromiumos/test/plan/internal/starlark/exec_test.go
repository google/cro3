// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package starlark_test

import (
	"chromiumos/test/plan/internal/starlark"
	"context"
	"io/ioutil"
	"os"
	"path"
	"strings"
	"testing"

	"github.com/google/go-cmp/cmp"
	configpb "go.chromium.org/chromiumos/config/go/api"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/payload"
	test_api "go.chromium.org/chromiumos/config/go/test/api"
	test_api_v1 "go.chromium.org/chromiumos/config/go/test/api/v1"
	"google.golang.org/protobuf/testing/protocmp"
)

var buildMetadataList = &buildpb.SystemImage_BuildMetadataList{
	Values: []*buildpb.SystemImage_BuildMetadata{
		{
			BuildTarget: &buildpb.SystemImage_BuildTarget{
				PortageBuildTarget: &buildpb.Portage_BuildTarget{OverlayName: "overlay1"},
			},
		},
		{
			BuildTarget: &buildpb.SystemImage_BuildTarget{
				PortageBuildTarget: &buildpb.Portage_BuildTarget{OverlayName: "overlay2"},
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

func TestExecTestPlan(t *testing.T) {
	ctx := context.Background()
	starlarkSource := `
load("@proto//chromiumos/test/api/v1/plan.proto", plan_pb = "chromiumos.test.api.v1")
load("@proto//chromiumos/test/api/coverage_rule.proto", coverage_rule_pb = "chromiumos.test.api")
load("@proto//lab/license.proto", licence_pb = "lab")

build_metadata = testplan.get_build_metadata()
config_bundles = testplan.get_config_bundle_list()
print('Got {} BuildMetadatas'.format(len(build_metadata.values)))
print('Got {} ConfigBundles'.format(len(config_bundles.values)))
coverage_rule_a = coverage_rule_pb.CoverageRule(name='ruleA')
coverage_rule_b = coverage_rule_pb.CoverageRule(name='ruleB')
test_licence = licence_pb.LICENSE_TYPE_WINDOWS_10_PRO
testplan.add_hw_test_plan(
	plan_pb.HWTestPlan(
		id=plan_pb.HWTestPlan.TestPlanId(value='plan1'),
		coverage_rules=[coverage_rule_a],
	),
)
testplan.add_vm_test_plan(
	plan_pb.VMTestPlan(
		id=plan_pb.VMTestPlan.TestPlanId(value='vm_plan2'),
		coverage_rules=[coverage_rule_b],
	)
)
`
	planFilename := writeTempStarlarkFile(
		t, starlarkSource,
	)

	hwTestPlans, vmTestPlans, err := starlark.ExecTestPlan(
		ctx,
		planFilename,
		buildMetadataList,
		configBundleList,
	)

	if err != nil {
		t.Fatalf("ExecTestPlan failed: %s", err)
	}

	expectedHwTestPlans := []*test_api_v1.HWTestPlan{
		{
			Id: &test_api_v1.HWTestPlan_TestPlanId{Value: "plan1"},
			CoverageRules: []*test_api.CoverageRule{
				{
					Name: "ruleA",
				},
			},
		},
	}

	expectedVmTestPlans := []*test_api_v1.VMTestPlan{
		{
			Id: &test_api_v1.VMTestPlan_TestPlanId{Value: "vm_plan2"},
			CoverageRules: []*test_api.CoverageRule{
				{
					Name: "ruleB",
				},
			},
		},
	}

	if len(expectedHwTestPlans) != len(hwTestPlans) {
		t.Errorf("expected %d test plans, got %d", len(expectedHwTestPlans), len(hwTestPlans))
	}

	for i, expected := range expectedHwTestPlans {
		if diff := cmp.Diff(expected, hwTestPlans[i], protocmp.Transform()); diff != "" {
			t.Errorf("returned unexpected diff in test plan %d (-want +got):\n%s", i, diff)
		}
	}

	if len(expectedVmTestPlans) != len(vmTestPlans) {
		t.Errorf("expected %d test plans, got %d", len(expectedVmTestPlans), len(vmTestPlans))
	}

	for i, expected := range expectedVmTestPlans {
		if diff := cmp.Diff(expected, vmTestPlans[i], protocmp.Transform()); diff != "" {
			t.Errorf("returned unexpected diff in test plan %d (-want +got):\n%s", i, diff)
		}
	}
}

func TestExecTestPlanErrors(t *testing.T) {
	ctx := context.Background()

	tests := []struct {
		name           string
		starlarkSource string
		err            string
	}{
		{
			name:           "invalid positional args",
			starlarkSource: "testplan.get_build_metadata(1, 2)",
			err:            "get_build_metadata: got 2 arguments, want at most 0",
		},
		{
			name:           "invalid named args",
			starlarkSource: "testplan.get_config_bundle_list(somearg='abc')",
			err:            "get_config_bundle_list: unexpected keyword argument \"somearg\"",
		},
		{
			name:           "invalid named args ctor HW",
			starlarkSource: "testplan.add_hw_test_plan(somearg='abc')",
			err:            "add_hw_test_plan: unexpected keyword argument \"somearg\"",
		},
		{
			name:           "invalid named args ctor VM",
			starlarkSource: "testplan.add_vm_test_plan(somearg='abc')",
			err:            "add_vm_test_plan: unexpected keyword argument \"somearg\"",
		},
		{
			name:           "invalid type ctor HW",
			starlarkSource: "testplan.add_hw_test_plan(hw_test_plan='abc')",
			err:            "add_hw_test_plan: arg must be a chromiumos.test.api.v1.HWTestPlan, got \"\\\"abc\\\"\"",
		},
		{
			name:           "invalid type ctor VM",
			starlarkSource: "testplan.add_vm_test_plan(vm_test_plan='abc')",
			err:            "add_vm_test_plan: arg must be a chromiumos.test.api.v1.VMTestPlan, got \"\\\"abc\\\"\"",
		},
		{
			name: "invalid proto ctor",
			starlarkSource: `
load("@proto//chromiumos/test/api/v1/plan.proto", plan_pb = "chromiumos.test.api.v1")
testplan.add_hw_test_plan(hw_test_plan=plan_pb.HWTestPlan.TestPlanId(value='abc'))
			`,
			err: "add_hw_test_plan: arg must be a chromiumos.test.api.v1.HWTestPlan, got \"value:\\\"abc\\\"\"",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			planFilename := writeTempStarlarkFile(
				t, tc.starlarkSource,
			)

			_, _, err := starlark.ExecTestPlan(
				ctx, planFilename, buildMetadataList, configBundleList,
			)

			if err == nil {
				t.Errorf("Expected error from ExecTestPlan")
			}

			if !strings.Contains(err.Error(), tc.err) {
				t.Errorf("Expected error message %q, got %q", tc.err, err.Error())
			}
		})
	}
}
