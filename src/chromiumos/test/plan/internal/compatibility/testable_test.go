// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package compatibility_test

import (
	"chromiumos/test/plan/internal/compatibility"
	"regexp"
	"testing"

	"github.com/google/go-cmp/cmp"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	test_api_v1 "go.chromium.org/chromiumos/config/go/test/api/v1"
	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"
	bbpb "go.chromium.org/luci/buildbucket/proto"
)

// coverageRule returns a CoverageRule with programs as the values for
// attr-program and provisionConfig (which may be nil).
func coverageRule(programs []string, provisionConfig *testpb.ProvisionConfig) *testpb.CoverageRule {
	return &testpb.CoverageRule{
		DutTargets: []*testpb.DutTarget{
			{
				Criteria: []*testpb.DutCriterion{
					{
						AttributeId: &testpb.DutAttribute_Id{Value: "attr-program"},
						Values:      programs,
					},
				},
				ProvisionConfig: provisionConfig,
			},
		},
	}
}

// testBuild returns a Build proto with buildTarget as an input property.
func testBuild(t *testing.T, name, buildTarget string) *bbpb.Build {
	return &bbpb.Build{
		Builder: &bbpb.BuilderID{Builder: name},
		Input: &bbpb.Build_Input{
			Properties: newStruct(t, map[string]interface{}{
				"build_target": map[string]interface{}{
					"name": buildTarget,
				},
			}),
		},
	}
}

func TestTestableBuilds(t *testing.T) {
	// Use BuilderConfigs to specify the asan profile for cq-vm-asan.
	builderConfigs := &chromiumos.BuilderConfigs{
		BuilderConfigs: []*chromiumos.BuilderConfig{
			{
				Id: &chromiumos.BuilderConfig_Id{
					Name: "cq-vm-asan",
				},
				Build: &chromiumos.BuilderConfig_Build{
					PortageProfile: &chromiumos.BuilderConfig_Build_PortageProfile{
						Profile: "asan",
					},
				},
			},
		},
	}

	testCases := []struct {
		name             string
		hwCoverageRules  []*testpb.CoverageRule
		vmCoverageRules  []*testpb.CoverageRule
		builds           []*bbpb.Build
		expectedBuilders []string
	}{
		// boardA and boardD are included by CoverageRules, nottestable is not.
		{
			name: "some testable builders",
			hwCoverageRules: []*testpb.CoverageRule{
				coverageRule([]string{"boardA", "boardB"}, nil),
				coverageRule([]string{"boardD"}, nil),
			},
			vmCoverageRules: []*testpb.CoverageRule{},
			builds: []*bbpb.Build{
				testBuild(t, "cq-boardA", "boardA"),
				testBuild(t, "cq-boardD", "boardD"),
				testBuild(t, "cq-nottestable", "nottestable"),
			},
			expectedBuilders: []string{"cq-boardA", "cq-boardD"},
		},
		// boardA-kernelnext is included by the CoverageRule, regular boardA is
		// not.
		{
			name: "variant builders",
			hwCoverageRules: []*testpb.CoverageRule{
				coverageRule(
					[]string{"boardA"},
					&testpb.ProvisionConfig{BoardVariant: "kernelnext"},
				),
			},
			vmCoverageRules: nil,
			builds: []*bbpb.Build{
				testBuild(t, "cq-boardA-kernelnext", "boardA-kernelnext"),
				testBuild(t, "cq-boardA", "boardA"),
			},
			expectedBuilders: []string{"cq-boardA-kernelnext"},
		},
		// The cq-vm-asan builder (which is configured to use the "asan"
		// profile by builderConfigs) is included, the regular cq-vm builder is
		// not.
		{
			name:            "profile builders",
			hwCoverageRules: nil,
			vmCoverageRules: []*testpb.CoverageRule{
				coverageRule(
					[]string{"vmBoard"},
					&testpb.ProvisionConfig{Profile: "asan"},
				),
			},
			builds: []*bbpb.Build{
				testBuild(t, "cq-vm-asan", "vmBoard"),
				testBuild(t, "cq-vm", "vmBoard"),
			},
			expectedBuilders: []string{"cq-vm-asan"},
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			builds, err := compatibility.TestableBuilds(
				[]*test_api_v1.HWTestPlan{
					{
						CoverageRules: tc.hwCoverageRules,
					},
				},
				[]*test_api_v1.VMTestPlan{
					{
						CoverageRules: tc.vmCoverageRules,
					},
				},
				tc.builds,
				builderConfigs,
				dutAttributeList,
			)

			if err != nil {
				t.Fatal(err)
			}

			builderNames := []string{}
			for _, build := range builds {
				builderNames = append(builderNames, build.GetBuilder().GetBuilder())
			}

			if diff := cmp.Diff(tc.expectedBuilders, builderNames); diff != "" {
				t.Errorf("TestableBuilds returned unexpected diff (-want +got):\n%s", diff)
			}
		})
	}
}

func TestTestableBuildsErrors(t *testing.T) {
	testCases := []struct {
		name            string
		hwCoverageRules []*testpb.CoverageRule
		builds          []*bbpb.Build
		errRegexp       string
	}{
		{
			name: "multiple DutTargets",
			hwCoverageRules: []*testpb.CoverageRule{
				{
					DutTargets: []*testpb.DutTarget{
						{
							Criteria: []*testpb.DutCriterion{
								{
									AttributeId: &testpb.DutAttribute_Id{Value: "attr-program"},
									Values:      []string{"a", "b"},
								},
							},
						},
						{
							Criteria: []*testpb.DutCriterion{
								{
									AttributeId: &testpb.DutAttribute_Id{Value: "attr-program"},
									Values:      []string{"c", "d"},
								},
							},
						},
					},
				},
			},
			builds:    []*bbpb.Build{testBuild(t, "builderA", "boardA")},
			errRegexp: "expected exactly one DutTarget in CoverageRule",
		},
		{
			name: "multiple program attrs",
			hwCoverageRules: []*testpb.CoverageRule{
				{
					DutTargets: []*testpb.DutTarget{
						{
							Criteria: []*testpb.DutCriterion{
								{
									AttributeId: &testpb.DutAttribute_Id{Value: "attr-program"},
									Values:      []string{"a", "b"},
								},
								{
									AttributeId: &testpb.DutAttribute_Id{Value: "attr-program"},
									Values:      []string{"c", "d"},
								},
							},
						},
					},
				},
			},
			builds:    []*bbpb.Build{testBuild(t, "builderA", "boardA")},
			errRegexp: "DutAttribute.+specified twice",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := compatibility.TestableBuilds(
				[]*test_api_v1.HWTestPlan{
					{
						CoverageRules: tc.hwCoverageRules,
					},
				},
				[]*test_api_v1.VMTestPlan{},
				tc.builds,
				builderConfigs,
				dutAttributeList,
			)
			if err == nil {
				t.Fatal("Expected error from TestableBuilds")
			}

			matched, reErr := regexp.Match(tc.errRegexp, []byte(err.Error()))
			if reErr != nil {
				t.Fatal(reErr)
			}

			if !matched {
				t.Errorf("Expected error to match regexp %q, got %q", tc.errRegexp, err.Error())
			}
		})
	}
}
