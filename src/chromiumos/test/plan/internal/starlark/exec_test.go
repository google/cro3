// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package starlark_test

import (
	"chromiumos/test/plan/internal/starlark"
	"os"
	"path"
	"strings"
	"testing"

	"go.chromium.org/chromiumos/config/go/api"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/payload"
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

	if err := os.WriteFile(
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
`
	planFilename := writeTempStarlarkFile(
		t, starlarkSource,
	)

	err := starlark.ExecTestPlan(
		planFilename,
		buildMetadataList,
		flatConfigList,
	)

	if err != nil {
		t.Errorf("ExecTestPlan failed: %s", err)
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
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			planFilename := writeTempStarlarkFile(
				t, tc.starlarkSource,
			)

			err := starlark.ExecTestPlan(
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
