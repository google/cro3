// Copyright 2022 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// Package compatibility provides functions for backwards compatiblity with
// test platform.
package compatibility

import (
	"fmt"
	"math/rand"
	"strings"

	"chromiumos/test/plan/internal/compatibility/priority"

	"github.com/golang/glog"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	test_api_v1 "go.chromium.org/chromiumos/config/go/test/api/v1"
	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"
	"go.chromium.org/chromiumos/infra/proto/go/testplans"
	bbpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/data/stringset"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/structpb"
	"google.golang.org/protobuf/types/known/wrapperspb"
)

// getAttrFromCriteria finds the DutCriterion with attribute id attr in
// criteria. If the DutCriterion is not found an error is returned.
func getAttrFromCriteria(criteria []*testpb.DutCriterion, attr *testpb.DutAttribute) ([]string, error) {
	for _, criterion := range criteria {
		isAttr := false
		if criterion.GetAttributeId().GetValue() == attr.GetId().GetValue() {
			isAttr = true
		} else {
			for _, alias := range attr.GetAliases() {
				if criterion.GetAttributeId().GetValue() == alias {
					isAttr = true
					break
				}
			}
		}

		if isAttr {
			if len(criterion.GetValues()) == 0 {
				return nil, fmt.Errorf("only DutCriterion with at least one value supported, got %q", criterion)
			}

			return criterion.GetValues(), nil
		}
	}

	return nil, fmt.Errorf("attribute %q not found in DutCriterion %q", attr.GetId().GetValue(), criteria)
}

// Chooses a program from the options in programs to test. The choice is
// determined by:
// 1. Choose a program with a critial completed build. If there are multiple
// programs, choose with prioritySelector.
//
// 2. Choose a program with a non-critial completed build. If there are multiple
// programs, choose with prioritySelector.
//
// 3. Choose a program with prioritySelector.
func chooseProgramToTest(
	pool string,
	programs []string,
	buildInfos map[string]*buildInfo,
	prioritySelector *priority.RandomWeightedSelector,
) (string, error) {
	var criticalPrograms, completedPrograms []string
	for _, program := range programs {
		buildInfo, found := buildInfos[program]
		if found {
			completedPrograms = append(completedPrograms, program)

			if buildInfo.criticality == bbpb.Trinary_YES {
				criticalPrograms = append(criticalPrograms, program)
			}
		}
	}

	if len(criticalPrograms) > 0 {
		glog.V(2).Infof("Choosing between critical programs: %q", criticalPrograms)
		return prioritySelector.Select(pool, criticalPrograms)
	}

	if len(completedPrograms) > 0 {
		glog.V(2).Infof("Choosing between completed programs: %q", completedPrograms)
		return prioritySelector.Select(pool, completedPrograms)
	}

	glog.V(2).Info("No completed programs found.")
	return prioritySelector.Select(pool, programs)
}

// extractFromProtoStruct returns the path pointed to by fields. For example,
// for the struct `"a": {"b": 1}`, if fields is ["a", "b"], 1 is returned. The
// bool return value indicates if the path was found.
func extractFromProtoStruct(s *structpb.Struct, fields ...string) (*structpb.Value, bool) {
	var value *structpb.Value

	for i, field := range fields {
		var ok bool
		value, ok = s.Fields[field]
		if !ok {
			return nil, false
		}

		// All of the fields before the last one must be structs (otherwise
		// fields cannot form a valid path). Since the last field may not be a
		// struct, (and we don't need to use the struct if it is) break here and
		// return the value. Otherwise check that the value is a struct, and
		// set s to the new struct.
		if i == len(fields)-1 {
			break
		}

		s = value.GetStructValue()
		if s == nil {
			return nil, false
		}
	}

	return value, true
}

// extractStringFromProtoStruct invokes extractFromProtoStruct, but also checks
// that the value pointed to by fields is a non-empty string.
func extractStringFromProtoStruct(s *structpb.Struct, fields ...string) (string, bool) {
	v, ok := extractFromProtoStruct(s, fields...)
	if !ok {
		return "", false
	}

	if v.GetStringValue() == "" {
		return "", false
	}

	return v.GetStringValue(), true
}

// buildInfo describes properties parsed from a Buildbucket build.
type buildInfo struct {
	buildTarget string
	builderName string
	criticality bbpb.Trinary
	payload     *testplans.BuildPayload
}

// parseBuildProtos parses serialized Buildbucket Build protos and extracts
// properties into buildInfos.
func parseBuildProtos(buildbucketProtos []*testplans.ProtoBytes) ([]*buildInfo, error) {
	buildInfos := []*buildInfo{}

	// The presence of any one of these artifacts is enough to tell us that this
	// build should be considered for testing.
	testArtifacts := stringset.NewFromSlice(
		"AUTOTEST_FILES",
		"IMAGE_ZIP",
		"PINNED_GUEST_IMAGES",
		"TAST_FILES",
		"TEST_UPDATE_PAYLOAD",
	)

	for _, protoBytes := range buildbucketProtos {
		build := &bbpb.Build{}
		if err := proto.Unmarshal(protoBytes.SerializedProto, build); err != nil {
			return nil, err
		}

		pointless, ok := extractFromProtoStruct(build.GetOutput().GetProperties(), "pointless_build")
		if ok && pointless.GetBoolValue() {
			glog.Warningf("build %q is pointless, skipping", build.GetBuilder().GetBuilder())
			continue
		}

		buildTarget, ok := extractStringFromProtoStruct(
			build.GetInput().GetProperties(),
			"build_target", "name",
		)
		if !ok {
			glog.Warningf("build_target.name not found in input properties of build %q, skipping", build.GetBuilder().GetBuilder())
			continue
		}

		filesByArtifact, ok := extractFromProtoStruct(
			build.GetOutput().GetProperties(),
			"artifacts", "files_by_artifact",
		)
		if !ok {
			glog.Warningf("artifacts.files_by_artifact not found in output properties of build %q, skipping", build.GetBuilder().GetBuilder())
			continue
		}

		if filesByArtifact.GetStructValue() == nil {
			return nil, fmt.Errorf("artifacts.files_by_artifact must be a non-empty struct")
		}

		foundTestArtifact := false
		for field := range filesByArtifact.GetStructValue().GetFields() {
			if testArtifacts.Has(field) {
				foundTestArtifact = true
				break
			}
		}

		if !foundTestArtifact {
			glog.Warningf("no test artifacts found for build %q, skipping", build.GetBuilder().GetBuilder())
			continue
		}

		artifacts_gs_bucket, ok := extractStringFromProtoStruct(
			build.GetOutput().GetProperties(),
			"artifacts", "gs_bucket",
		)
		if !ok {
			return nil, fmt.Errorf("artifacts.gs_bucket not found for build %q", build.GetBuilder().GetBuilder())
		}

		artifacts_gs_path, ok := extractStringFromProtoStruct(
			build.GetOutput().GetProperties(),
			"artifacts", "gs_path",
		)
		if !ok {
			return nil, fmt.Errorf("artifacts.gs_path not found for build %q", build.GetBuilder().GetBuilder())
		}

		buildInfos = append(buildInfos, &buildInfo{
			buildTarget: buildTarget,
			builderName: build.GetBuilder().GetBuilder(),
			criticality: build.GetCritical(),
			payload: &testplans.BuildPayload{
				ArtifactsGsBucket: artifacts_gs_bucket,
				ArtifactsGsPath:   artifacts_gs_path,
				FilesByArtifact:   filesByArtifact.GetStructValue(),
			},
		},
		)
	}

	return buildInfos, nil
}

// Defines the environment a test should run in, e.g. hardware, Tast on VM, Tast
// on GCE.
type testEnvironment int64

const (
	Undefined testEnvironment = iota
	HW
	TastVM
	TastGCE
)

// suiteInfo is a struct internal to this package to track information about a
// test suite to run.
type suiteInfo struct {
	// program that was chosen to run the suite on
	program string
	// pool to run the suite in.
	pool string
	// name of the suite.
	suite string
	// environment to run the suite in.
	environment testEnvironment
	// tastExpr that defines the suite. Only valid if environment is TastVM or
	// TastGCE
	tastExpr string
}

// tagCriteriaToTastExpr converts a TestCaseTagCriteria to a Tast expression.
// All of the included and excluded tags in criteria are joined together with
// " && ", i.e. Tast expressions with "|" cannot be generated. Excluded tags are
// negated with "!".
//
// See https://chromium.googlesource.com/chromiumos/platform/tast/+/HEAD/docs/running_tests.md
// for a description of Tast expressions.
func tagCriteriaToTastExpr(criteria testpb.TestSuite_TestCaseTagCriteria) string {
	attributes := criteria.GetTags()
	for _, tag := range criteria.GetTagExcludes() {
		attributes = append(attributes, "!"+tag)
	}

	return strings.Join(attributes, " && ")
}

// coverageRuleToSuiteInfo converts a CoverageRule (CTPv2 compatible) to a
// suiteInfo (internal representation used by this package).
//
// coverageRuleToSuiteInfo does the following steps:
// 1. Extract the pool and program attrs from rule, failing if they are not
// present.
// 2. Choose a program using prioritySelector.
// 3. Convert each TestSuite (CTPv2 compatible) in rule into a suiteInfo, using
// either the tag criteria or test case id list.
func coverageRuleToSuiteInfo(
	rule *testpb.CoverageRule,
	poolAttr, programAttr *testpb.DutAttribute,
	boardToBuildInfo map[string]*buildInfo,
	prioritySelector *priority.RandomWeightedSelector,
	env testEnvironment,
) ([]*suiteInfo, error) {
	if len(rule.GetDutTargets()) != 1 {
		return nil, fmt.Errorf("expected exactly one DutTarget in CoverageRule, got %q", rule)
	}

	dutTarget := rule.GetDutTargets()[0]

	pools, err := getAttrFromCriteria(dutTarget.GetCriteria(), poolAttr)
	if err != nil {
		return nil, err
	}

	if len(pools) != 1 {
		return nil, fmt.Errorf("only DutCriteria with exactly one \"pool\" argument are supported, got %q", pools)
	}

	pool := pools[0]

	programs, err := getAttrFromCriteria(dutTarget.GetCriteria(), programAttr)
	if err != nil {
		return nil, err
	}

	chosenProgram, err := chooseProgramToTest(
		pool, programs, boardToBuildInfo, prioritySelector,
	)
	if err != nil {
		return nil, err
	}
	glog.V(2).Infof("chose program %q from possible programs %q", chosenProgram, programs)

	if len(dutTarget.GetCriteria()) != 2 {
		return nil, fmt.Errorf(
			"expected DutTarget to use exactly criteria %q and %q, got %q",
			programAttr.GetId().GetValue(), poolAttr.GetId().GetValue(), dutTarget,
		)
	}

	var suiteInfos []*suiteInfo
	for _, suite := range rule.GetTestSuites() {
		switch spec := suite.Spec.(type) {
		case *testpb.TestSuite_TestCaseIds:
			if env != HW {
				return nil, fmt.Errorf("TestCaseIdLists are only valid for HW tests")
			}
			for _, id := range spec.TestCaseIds.GetTestCaseIds() {
				suiteInfos = append(
					suiteInfos,
					&suiteInfo{
						program:     chosenProgram,
						pool:        pool,
						suite:       id.Value,
						environment: env,
					})
			}
		case *testpb.TestSuite_TestCaseTagCriteria_:
			if env != TastVM {
				return nil, fmt.Errorf("TestCaseTagCriteria are only valid for VM tests")
			}
			suiteInfos = append(suiteInfos,
				&suiteInfo{
					program:     chosenProgram,
					pool:        pool,
					suite:       suite.GetName(),
					tastExpr:    tagCriteriaToTastExpr(*spec.TestCaseTagCriteria),
					environment: env,
				})
		default:
			return nil, fmt.Errorf("TestSuite spec type %T is not supported", spec)
		}

	}

	return suiteInfos, nil
}

// extractSuiteInfos returns a map from program name to suiteInfos for the
// program. There is one suiteInfo per CoverageRule in hwTestPlans and
// vmTestPlans.
func extractSuiteInfos(
	rnd *rand.Rand,
	hwTestPlans []*test_api_v1.HWTestPlan,
	vmTestPlans []*test_api_v1.VMTestPlan,
	dutAttributeList *testpb.DutAttributeList,
	boardPriorityList *testplans.BoardPriorityList,
	boardToBuildInfo map[string]*buildInfo,
) (map[string][]*suiteInfo, error) {
	// Find the program and pool attributes in the DutAttributeList.
	var programAttr, poolAttr *testpb.DutAttribute
	for _, attr := range dutAttributeList.GetDutAttributes() {
		if attr.Id.Value == "attr-program" {
			programAttr = attr
		} else if attr.Id.Value == "swarming-pool" {
			poolAttr = attr
		}
	}

	if programAttr == nil {
		return nil, fmt.Errorf("\"attr-program\" not found in DutAttributeList")
	}

	if poolAttr == nil {
		return nil, fmt.Errorf("\"swarming-pool\" not found in DutAttributeList")
	}

	programToSuiteInfos := map[string][]*suiteInfo{}
	prioritySelector := priority.NewRandomWeightedSelector(
		rnd,
		boardPriorityList,
	)

	for _, hwTestPlan := range hwTestPlans {
		for _, rule := range hwTestPlan.GetCoverageRules() {
			suiteInfos, err := coverageRuleToSuiteInfo(
				rule, poolAttr, programAttr, boardToBuildInfo, prioritySelector, HW,
			)
			if err != nil {
				return nil, err
			}

			for _, info := range suiteInfos {
				chosenProgram := info.program
				if _, ok := programToSuiteInfos[chosenProgram]; !ok {
					programToSuiteInfos[chosenProgram] = []*suiteInfo{}
				}

				programToSuiteInfos[chosenProgram] = append(programToSuiteInfos[chosenProgram], info)
			}
		}
	}

	for _, vmTestPlan := range vmTestPlans {
		for _, rule := range vmTestPlan.GetCoverageRules() {
			suiteInfos, err := coverageRuleToSuiteInfo(
				rule, poolAttr, programAttr, boardToBuildInfo, prioritySelector, TastVM,
			)
			if err != nil {
				return nil, err
			}

			for _, info := range suiteInfos {
				chosenProgram := info.program
				if _, ok := programToSuiteInfos[chosenProgram]; !ok {
					programToSuiteInfos[chosenProgram] = []*suiteInfo{}
				}

				programToSuiteInfos[chosenProgram] = append(programToSuiteInfos[chosenProgram], info)
			}
		}
	}

	return programToSuiteInfos, nil
}

// ToCTP1 converts a [VM|HW]TestPlan to a GenerateTestPlansResponse, which can
// be used with CTP1.
//
// [HW|VM]TestPlan protos target CTP2, this method is meant to provide backwards
// compatibility with CTP1. Because CTP1 does not support rules-based testing,
// there are some limitations to the [HW|VM]TestPlans that can be converted:
// - Both the "attr-program" and "swarming-pool" DutAttributes must be used in
// each DutTarget, and only these DutAttributes are allowed, i.e. each DutTarget
// must use exactly these attributes.
//
// - Multiple values for "attr-program" are allowed, a program will be chosen
// randomly proportional to the board's priority in boardPriorityList (lowest
// priority is most likely to get chosen, negative priorities are allowed,
// programs without a priority get priority 0).
//
// - Only TestCaseIds are supported (no tag-based testing). generateTestPlanReq
// is needed to provide Build protos for the builds being tested.
// dutAttributeList must contain the "attr-program" and "swarming-pool"
// DutAttributes.
func ToCTP1(
	rnd *rand.Rand,
	hwTestPlans []*test_api_v1.HWTestPlan,
	vmTestPlans []*test_api_v1.VMTestPlan,
	generateTestPlanReq *testplans.GenerateTestPlanRequest,
	dutAttributeList *testpb.DutAttributeList,
	boardPriorityList *testplans.BoardPriorityList,
) (*testplans.GenerateTestPlanResponse, error) {
	buildInfos, err := parseBuildProtos(generateTestPlanReq.GetBuildbucketProtos())
	if err != nil {
		return nil, err
	}

	// Form maps from board to buildInfo, which will be needed by calls to
	// extractSuiteInfos.
	boardToBuildInfo := map[string]*buildInfo{}
	for _, buildInfo := range buildInfos {
		boardToBuildInfo[buildInfo.buildTarget] = buildInfo
	}

	programToSuiteInfos, err := extractSuiteInfos(
		rnd, hwTestPlans, vmTestPlans, dutAttributeList, boardPriorityList, boardToBuildInfo,
	)
	if err != nil {
		return nil, err
	}

	var hwTestUnits []*testplans.HwTestUnit
	// TODO(b/218319842): Support backwards compatibility for TastGceTestUnit
	// as well.
	var vmTestUnits []*testplans.TastVmTestUnit

	// Join the buildInfos and suiteInfos on the suite's program name and
	// build's build target. Each build maps to one HwTestUnit, each suite maps
	// to one HwTestCfg_HwTest.
	for _, buildInfo := range buildInfos {
		suiteInfos, ok := programToSuiteInfos[buildInfo.buildTarget]
		if !ok {
			glog.Warningf("no suites found for build %q, skipping tests", buildInfo.buildTarget)
			continue
		}

		var hwTests []*testplans.HwTestCfg_HwTest
		var tastVMTests []*testplans.TastVmTestCfg_TastVmTest
		for _, suiteInfo := range suiteInfos {
			switch env := suiteInfo.environment; env {
			case HW:
				hwTests = append(hwTests, &testplans.HwTestCfg_HwTest{
					Suite:       suiteInfo.suite,
					SkylabBoard: suiteInfo.program,
					Pool:        suiteInfo.pool,
					Common: &testplans.TestSuiteCommon{
						DisplayName: fmt.Sprintf("%s.%s", suiteInfo.program, suiteInfo.suite),
						// TODO(b/218319842): Set critical value based on v2 test disablement config.
						Critical: &wrapperspb.BoolValue{
							Value: true,
						},
					},
				})

				glog.V(2).Infof("added HwTest %q", hwTests[len(hwTests)-1])
			case TastVM:
				tastVMTests = append(tastVMTests, &testplans.TastVmTestCfg_TastVmTest{
					SuiteName: suiteInfo.suite,
					TastTestExpr: []*testplans.TastVmTestCfg_TastTestExpr{
						{
							TestExpr: suiteInfo.tastExpr,
						},
					},
				})
				glog.V(2).Infof("added TastVmTest %q", tastVMTests[len(tastVMTests)-1])
			default:
				return nil, fmt.Errorf("unsupported environment %T", env)
			}
		}

		common := &testplans.TestUnitCommon{
			BuildTarget: &chromiumos.BuildTarget{
				Name: buildInfo.buildTarget,
			},
			BuilderName:  buildInfo.builderName,
			BuildPayload: buildInfo.payload,
		}

		if len(hwTests) > 0 {
			hwTestUnit := &testplans.HwTestUnit{
				Common: common,
				HwTestCfg: &testplans.HwTestCfg{
					HwTest: hwTests,
				},
			}
			hwTestUnits = append(hwTestUnits, hwTestUnit)
		} else if len(tastVMTests) > 0 {
			vmTestUnit := &testplans.TastVmTestUnit{
				Common: common,
				TastVmTestCfg: &testplans.TastVmTestCfg{
					TastVmTest: tastVMTests,
				},
			}
			vmTestUnits = append(vmTestUnits, vmTestUnit)
		}
	}

	return &testplans.GenerateTestPlanResponse{
		HwTestUnits:           hwTestUnits,
		DirectTastVmTestUnits: vmTestUnits,
	}, nil
}
