// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package starlark_test

import (
	"chromiumos/test/plan/internal/starlark"
	"io/ioutil"
	"os"
	"path"
	"strings"
	"testing"

	"github.com/google/go-cmp/cmp"
	"go.chromium.org/chromiumos/config/go/api"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/payload"
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

var flatConfigList = &payload.FlatConfigList{
	Values: []*payload.FlatConfig{
		{
			Program: &api.Program{
				Name: "progA",
			},
		},
		{
			Program: &api.Program{
				Name: "progB",
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
	starlarkSource := `
build_metadata = testplan.get_build_metadata()
flat_configs = testplan.get_flat_config_list()
print('Got {} BuildMetadatas'.format(len(build_metadata.values)))
print('Got {} FlatConfigs'.format(len(flat_configs.values)))
testplan.add_hw_test_plan(
	testplan.HWTestPlan(id=testplan.TestPlanId(value='plan1'))
)
`
	planFilename := writeTempStarlarkFile(
		t, starlarkSource,
	)

	testPlans, err := starlark.ExecTestPlan(
		planFilename,
		buildMetadataList,
		flatConfigList,
	)

	if err != nil {
		t.Errorf("ExecTestPlan failed: %s", err)
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

func TestExecTestPlanErrors(t *testing.T) {
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
			starlarkSource: "testplan.get_flat_config_list(somearg='abc')",
			err:            "get_flat_config_list: unexpected keyword argument \"somearg\"",
		},
		{
			name:           "invalid named args ctor",
			starlarkSource: "testplan.add_hw_test_plan(somearg='abc')",
			err:            "add_hw_test_plan: unexpected keyword argument \"somearg\"",
		},
		{
			name:           "invalid type ctor",
			starlarkSource: "testplan.add_hw_test_plan(hw_test_plan='abc')",
			err:            "arg to add_hw_test_plan must be a HWTestPlan, got \"\\\"abc\\\"\"",
		},
		{
			name:           "invalid proto ctor",
			starlarkSource: "testplan.add_hw_test_plan(hw_test_plan=testplan.TestPlanId(value='abc'))",
			err:            "arg to add_hw_test_plan must be a HWTestPlan, got \"value:\\\"abc\\\" ",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			planFilename := writeTempStarlarkFile(
				t, tc.starlarkSource,
			)

			_, err := starlark.ExecTestPlan(
				planFilename, buildMetadataList, flatConfigList,
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
