// Copyright 2022 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package compatibility_test

import (
	"chromiumos/test/plan/internal/compatibility"
	"strings"
	"testing"

	"github.com/golang/protobuf/proto"
	"github.com/google/go-cmp/cmp"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	test_api_v1 "go.chromium.org/chromiumos/config/go/test/api/v1"
	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"
	"go.chromium.org/chromiumos/infra/proto/go/testplans"
	bbpb "go.chromium.org/luci/buildbucket/proto"
	"google.golang.org/protobuf/testing/protocmp"
	"google.golang.org/protobuf/types/known/structpb"
	"google.golang.org/protobuf/types/known/wrapperspb"
)

// newStruct is a convenience method to build a structpb.Struct from a map of
// string -> interface. For example:
//
// newStruct(t, map[string]interface{}{
//   "a": 1, "b": []interface{}{"c", "d"}
// })
//
// Any errors will be passed to t.Fatal. See structpb.NewValue for more info
// on how Go interfaces are converted to structpb.Struct.
func newStruct(t *testing.T, fields map[string]interface{}) *structpb.Struct {
	s := &structpb.Struct{Fields: map[string]*structpb.Value{}}

	for key, val := range fields {
		valPb, err := structpb.NewValue(val)
		if err != nil {
			t.Fatal(err)
		}

		s.Fields[key] = valPb
	}

	return s
}

var hwTestPlans = []*test_api_v1.HWTestPlan{
	{
		CoverageRules: []*testpb.CoverageRule{
			{
				TestSuites: []*testpb.TestSuite{
					{
						Spec: &testpb.TestSuite_TestCaseIds{
							TestCaseIds: &testpb.TestCaseIdList{
								TestCaseIds: []*testpb.TestCase_Id{
									{
										Value: "suite1",
									},
									{
										Value: "suite2",
									},
								},
							},
						},
					},
				},
				DutTargets: []*testpb.DutTarget{
					{
						Criteria: []*testpb.DutCriterion{
							{
								AttributeId: &testpb.DutAttribute_Id{
									Value: "attr-design",
								},
								Values: []string{"boardA"},
							},
							{
								AttributeId: &testpb.DutAttribute_Id{
									Value: "swarming-pool",
								},
								Values: []string{"testpool"},
							},
						},
					},
				},
			},
		},
	},
}

func serializeOrFatal(t *testing.T, m proto.Message) *testplans.ProtoBytes {
	b, err := proto.Marshal(m)
	if err != nil {
		t.Fatal(err)
	}

	return &testplans.ProtoBytes{SerializedProto: b}
}

func getSerializedBuilds(t *testing.T) []*testplans.ProtoBytes {
	build1 := &bbpb.Build{
		Builder: &bbpb.BuilderID{
			Builder: "cq-builderA",
		},
		Input: &bbpb.Build_Input{
			Properties: newStruct(t, map[string]interface{}{
				"build_target": map[string]interface{}{
					"name": "boardA",
				},
			}),
		},
		Output: &bbpb.Build_Output{
			Properties: newStruct(t, map[string]interface{}{
				"artifacts": map[string]interface{}{
					"gs_bucket": "testgsbucket",
					"gs_path":   "testgspathA",
					"files_by_artifact": map[string]interface{}{
						"AUTOTEST_FILES": []interface{}{"file1", "file2"},
					},
				},
			}),
		},
	}

	build2 := &bbpb.Build{
		Builder: &bbpb.BuilderID{
			Builder: "cq-builderB",
		},
		Input: &bbpb.Build_Input{
			Properties: newStruct(t, map[string]interface{}{
				"build_target": map[string]interface{}{
					"name": "boardB",
				},
			}),
		},
		Output: &bbpb.Build_Output{
			Properties: newStruct(t, map[string]interface{}{
				"artifacts": map[string]interface{}{
					"gs_bucket": "testgsbucket",
					"gs_path":   "testgspathB",
					"files_by_artifact": map[string]interface{}{
						"testartifact": []interface{}{"file1", "file2"},
					},
				},
			}),
		},
	}

	build3 := &bbpb.Build{
		Builder: &bbpb.BuilderID{
			Builder: "pointless-build",
		},
		Output: &bbpb.Build_Output{
			Properties: newStruct(t, map[string]interface{}{
				"pointless_build": true,
			}),
		},
	}

	build4 := &bbpb.Build{
		Builder: &bbpb.BuilderID{
			Builder: "no-build-target-build",
		},
		Input: &bbpb.Build_Input{
			Properties: newStruct(t, map[string]interface{}{
				"other_input_prop": 12,
			}),
		},
		Output: &bbpb.Build_Output{
			Properties: newStruct(t, map[string]interface{}{
				"artifacts": map[string]interface{}{
					"gs_bucket": "testgsbucket",
					"gs_path":   "testgspathB",
					"files_by_artifact": map[string]interface{}{
						"testartifact": []interface{}{"file1", "file2"},
					},
				},
			}),
		},
	}

	return []*testplans.ProtoBytes{
		serializeOrFatal(t, build1),
		serializeOrFatal(t, build2),
		serializeOrFatal(t, build3),
		serializeOrFatal(t, build4),
	}
}

var dutAttributeList = &testpb.DutAttributeList{
	DutAttributes: []*testpb.DutAttribute{
		{
			Id: &testpb.DutAttribute_Id{
				Value: "attr-program",
			},
			Aliases: []string{"attr-design"},
		},
		{
			Id: &testpb.DutAttribute_Id{
				Value: "swarming-pool",
			},
		},
	},
}

func TestToCTP1(t *testing.T) {
	req := &testplans.GenerateTestPlanRequest{
		BuildbucketProtos: getSerializedBuilds(t),
	}

	resp, err := compatibility.ToCTP1(hwTestPlans, req, dutAttributeList)
	if err != nil {
		t.Fatal(err)
	}

	expectedResp := &testplans.GenerateTestPlanResponse{
		HwTestUnits: []*testplans.HwTestUnit{
			{
				Common: &testplans.TestUnitCommon{
					BuildTarget: &chromiumos.BuildTarget{
						Name: "boardA",
					},
					BuilderName: "cq-builderA",
					BuildPayload: &testplans.BuildPayload{
						ArtifactsGsBucket: "testgsbucket",
						ArtifactsGsPath:   "testgspathA",
						FilesByArtifact: newStruct(t, map[string]interface{}{
							"AUTOTEST_FILES": []interface{}{"file1", "file2"},
						}),
					},
				},
				HwTestCfg: &testplans.HwTestCfg{
					HwTest: []*testplans.HwTestCfg_HwTest{
						{
							Common: &testplans.TestSuiteCommon{
								DisplayName: "boardA.suite1",
								Critical:    wrapperspb.Bool(true),
							},
							Suite:       "suite1",
							SkylabBoard: "boardA",
							Pool:        "testpool",
						},
						{
							Common: &testplans.TestSuiteCommon{
								DisplayName: "boardA.suite2",
								Critical:    wrapperspb.Bool(true),
							},
							Suite:       "suite2",
							SkylabBoard: "boardA",
							Pool:        "testpool",
						},
					},
				},
			},
		},
	}
	if diff := cmp.Diff(expectedResp, resp, protocmp.Transform()); diff != "" {
		t.Errorf("ToCTP1Response returned unexpected diff (-want +got):\n%s", diff)
	}
}

func TestToCTP1Errors(t *testing.T) {
	testCases := []struct {
		name             string
		hwTestPlans      []*test_api_v1.HWTestPlan
		dutAttributeList *testpb.DutAttributeList
		err              string
	}{
		{
			name: "missing program DUT attribute",
			hwTestPlans: []*test_api_v1.HWTestPlan{
				{
					CoverageRules: []*testpb.CoverageRule{
						{
							DutTargets: []*testpb.DutTarget{
								{
									Criteria: []*testpb.DutCriterion{
										{
											AttributeId: &testpb.DutAttribute_Id{
												Value: "swarming-pool",
											},
											Values: []string{"testpool"},
										},
									},
								},
							},
						},
					},
				},
			},
			dutAttributeList: dutAttributeList,
			err:              "attribute \"attr-program\" not found in DutCriterion",
		},
		{
			name: "missing pool DUT attribute",
			hwTestPlans: []*test_api_v1.HWTestPlan{
				{
					CoverageRules: []*testpb.CoverageRule{
						{
							DutTargets: []*testpb.DutTarget{
								{
									Criteria: []*testpb.DutCriterion{
										{
											AttributeId: &testpb.DutAttribute_Id{
												Value: "attr-program",
											},
											Values: []string{"programA"},
										},
									},
								},
							},
						},
					},
				},
			},
			dutAttributeList: dutAttributeList,
			err:              "attribute \"swarming-pool\" not found in DutCriterion",
		},
		{
			name: "invalid DUT attribute",
			hwTestPlans: []*test_api_v1.HWTestPlan{
				{
					CoverageRules: []*testpb.CoverageRule{
						{
							DutTargets: []*testpb.DutTarget{
								{
									Criteria: []*testpb.DutCriterion{
										{
											AttributeId: &testpb.DutAttribute_Id{
												Value: "attr-program",
											},
											Values: []string{"programA"},
										},
										{
											AttributeId: &testpb.DutAttribute_Id{
												Value: "swarming-pool",
											},
											Values: []string{"testpool"},
										},
										{
											AttributeId: &testpb.DutAttribute_Id{
												Value: "fp",
											},
											Values: []string{"fp1"},
										},
									},
								},
							},
						},
					},
				},
			},
			dutAttributeList: dutAttributeList,
			err:              "expected DutTarget to use exactly criteria \"attr-program\" and \"swarming-pool\"",
		},
		{
			name: "multiple program values",
			hwTestPlans: []*test_api_v1.HWTestPlan{
				{
					CoverageRules: []*testpb.CoverageRule{
						{
							DutTargets: []*testpb.DutTarget{
								{
									Criteria: []*testpb.DutCriterion{
										{
											AttributeId: &testpb.DutAttribute_Id{
												Value: "attr-program",
											},
											Values: []string{"programA", "programB"},
										},
									},
								},
							},
						},
					},
				},
			},
			dutAttributeList: dutAttributeList,
			err:              "only DutCriterion with exactly one value supported",
		},
		{
			name: "test tags used",
			hwTestPlans: []*test_api_v1.HWTestPlan{
				{
					CoverageRules: []*testpb.CoverageRule{
						{
							DutTargets: []*testpb.DutTarget{
								{
									Criteria: []*testpb.DutCriterion{
										{
											AttributeId: &testpb.DutAttribute_Id{
												Value: "attr-program",
											},
											Values: []string{"programA"},
										},
										{
											AttributeId: &testpb.DutAttribute_Id{
												Value: "swarming-pool",
											},
											Values: []string{"testpool"},
										},
									},
								},
							},
							TestSuites: []*testpb.TestSuite{
								{
									Spec: &testpb.TestSuite_TestCaseTagCriteria_{
										TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
											Tags: []string{"kernel"},
										},
									},
								},
							},
						},
					},
				},
			},
			dutAttributeList: dutAttributeList,
			err:              "Only TestCaseIds supported in TestSuites",
		},
		{
			name: "multiple DUT targets",
			hwTestPlans: []*test_api_v1.HWTestPlan{
				{
					CoverageRules: []*testpb.CoverageRule{
						{
							DutTargets: []*testpb.DutTarget{
								{
									Criteria: []*testpb.DutCriterion{
										{
											AttributeId: &testpb.DutAttribute_Id{
												Value: "attr-program",
											},
											Values: []string{"programA"},
										},
									},
								},
								{
									Criteria: []*testpb.DutCriterion{
										{
											AttributeId: &testpb.DutAttribute_Id{
												Value: "attr-program",
											},
											Values: []string{"programB"},
										},
									},
								},
							},
						},
					},
				},
			},
			dutAttributeList: dutAttributeList,
			err:              "expected exactly one DutTarget in CoverageRule",
		},
		{
			name: "invalid DutAttributeList",
			dutAttributeList: &testpb.DutAttributeList{
				DutAttributes: []*testpb.DutAttribute{
					{
						Id: &testpb.DutAttribute_Id{
							Value: "otherdutattr",
						},
					},
				},
			},
			err: "\"attr-program\" not found in DutAttributeList",
		},
	}

	req := &testplans.GenerateTestPlanRequest{
		BuildbucketProtos: getSerializedBuilds(t),
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := compatibility.ToCTP1(tc.hwTestPlans, req, tc.dutAttributeList)
			if err == nil {
				t.Error("Expected error from ToCTP1")
			}

			if !strings.Contains(err.Error(), tc.err) {
				t.Errorf("Expected error to contain %q, got %q", tc.err, err.Error())
			}
		})
	}
}
