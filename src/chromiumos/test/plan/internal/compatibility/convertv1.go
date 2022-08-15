// Copyright 2022 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// Package compatibility provides functions for backwards compatiblity with
// test platform.
package compatibility

import (
	"errors"
	"fmt"
	"math/rand"
	"sort"
	"strings"

	"chromiumos/test/plan/internal/compatibility/priority"

	"github.com/golang/glog"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	test_api_v1 "go.chromium.org/chromiumos/config/go/test/api/v1"
	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"
	"go.chromium.org/chromiumos/infra/proto/go/lab"
	"go.chromium.org/chromiumos/infra/proto/go/testplans"
	bbpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/data/stringset"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/structpb"
	"google.golang.org/protobuf/types/known/wrapperspb"
)

// criterionMatchesAttribute returns true if criterion's AttributeId matches
// attr's Id or any of attr's Aliases.
func criterionMatchesAttribute(criterion *testpb.DutCriterion, attr *testpb.DutAttribute) bool {
	if criterion.GetAttributeId().GetValue() == attr.GetId().GetValue() {
		return true
	} else {
		for _, alias := range attr.GetAliases() {
			if criterion.GetAttributeId().GetValue() == alias {
				return true
			}
		}
	}

	return false
}

// getAttrFromCriteria finds the DutCriterion with attribute id attr in
// criteria. If the DutCriterion is not found a nil array is returned. If there
// is more than one DutCriterion that matches attr, an error is returned.
func getAttrFromCriteria(criteria []*testpb.DutCriterion, attr *testpb.DutAttribute) ([]string, error) {
	var values []string
	matched := false
	for _, criterion := range criteria {
		if criterionMatchesAttribute(criterion, attr) {
			if matched {
				return nil, fmt.Errorf("DutAttribute %q specified twice", attr)
			}

			if len(criterion.GetValues()) == 0 {
				return nil, fmt.Errorf("only DutCriterion with at least one value supported, got %q", criterion)
			}

			values = criterion.GetValues()
			matched = true
		}
	}

	return values, nil
}

// getAllAttrFromCriteria is similar to getAttrFromCriteria, but if more than
// one DutCriterion that matches attr, values for all matches are returned,
// instead of returning an error.
func getAllAttrFromCriteria(criteria []*testpb.DutCriterion, attr *testpb.DutAttribute) ([][]string, error) {
	var values [][]string
	for _, criterion := range criteria {
		if criterionMatchesAttribute(criterion, attr) {
			if len(criterion.GetValues()) == 0 {
				return nil, fmt.Errorf("only DutCriterion with at least one value supported, got %q", criterion)
			}

			values = append(values, criterion.GetValues())
		}
	}

	return values, nil
}

// checkCriteriaValid returns an error if any of criteria don't match the set
// of validAttrs.
func checkCriteriaValid(criteria []*testpb.DutCriterion, validAttrs ...*testpb.DutAttribute) error {
	for _, criterion := range criteria {
		matches := false
		for _, attr := range validAttrs {
			if criterionMatchesAttribute(criterion, attr) {
				matches = true
			}
		}

		if !matches {
			return fmt.Errorf("criterion %q doesn't match any valid attributes (%q)", criterion, validAttrs)
		}
	}

	return nil
}

// sortedValuesFromMap returns the values from m as a list, sorted by the keys
// of the map.
func sortedValuesFromMap[V any](m map[string]V) []V {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}

	sort.Strings(keys)

	values := make([]V, 0, len(m))
	for _, k := range keys {
		values = append(values, m[k])
	}

	return values
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
	// optional, design that was chosen to run the suite on
	design string
	// pool to run the suite in.
	pool string
	// name of the suite.
	suite string
	// environment to run the suite in.
	environment testEnvironment
	// tastExpr that defines the suite. Only valid if environment is TastVM or
	// TastGCE
	tastExpr string
	// optional, variant of the build target to test. For example, if program
	// is "coral" and boardVariant is "kernelnext", the "coral-kernelnext" build
	// will be used.
	boardVariant string
	// optional, the licenses required for the DUT the test will run on.
	licenses []lab.LicenseType
}

// getBuildTarget returns the build target for the suiteInfo. If boardVariant is
// set on the suite info, "<program>-<boardVariant>" is returned, otherwise
// "<program>" is returned.
func (si *suiteInfo) getBuildTarget() string {
	if len(si.boardVariant) > 0 {
		return fmt.Sprintf("%s-%s", si.program, si.boardVariant)
	}

	return si.program
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
// 1. Extract the relevant DutAttributes from rule. pool and program attributes
// are required.
// 2. Choose a program using prioritySelector.
// 3. Convert each TestSuite (CTPv2 compatible) in rule into a suiteInfo, using
// either the tag criteria or test case id list.
func coverageRuleToSuiteInfo(
	rule *testpb.CoverageRule,
	poolAttr, programAttr, designAttr, licenseAttr *testpb.DutAttribute,
	buildTargetToBuildInfo map[string]*buildInfo,
	prioritySelector *priority.RandomWeightedSelector,
	isVm bool,
) ([]*suiteInfo, error) {
	if len(rule.GetDutTargets()) != 1 {
		return nil, fmt.Errorf("expected exactly one DutTarget in CoverageRule, got %q", rule)
	}

	dutTarget := rule.GetDutTargets()[0]

	// Check that all criteria in dutTarget specify one of the expected
	// DutAttributes.
	if err := checkCriteriaValid(dutTarget.GetCriteria(), poolAttr, programAttr, designAttr, licenseAttr); err != nil {
		return nil, err
	}

	pools, err := getAttrFromCriteria(dutTarget.GetCriteria(), poolAttr)
	if err != nil {
		return nil, err
	}

	if len(pools) != 1 {
		return nil, fmt.Errorf("only DutCriteria with exactly one \"swarming-pool\" attribute are supported, got %q", pools)
	}

	pool := pools[0]

	programs, err := getAttrFromCriteria(dutTarget.GetCriteria(), programAttr)
	if err != nil {
		return nil, err
	}

	if len(programs) == 0 {
		return nil, errors.New("DutCriteria must contain at least one \"attr-program\" attribute")
	}

	// For simplicitly, only allow a board variant to be specified if a single
	// program is specified. I.e. a rule that specifies it wants to test the
	// "kernelnext" build chosen from multiple programs is not currently
	// supported.
	var chosenProgram string
	boardVariant := dutTarget.GetProvisionConfig().GetBoardVariant()
	if len(boardVariant) > 0 {
		if len(programs) != 1 {
			return nil, fmt.Errorf(
				"board_variant (%q) cannot be specified if multiple programs (%q) are specified",
				boardVariant, programs,
			)
		}

		chosenProgram = programs[0]
	} else {
		chosenProgram, err = chooseProgramToTest(
			pool, programs, buildTargetToBuildInfo, prioritySelector,
		)
		if err != nil {
			return nil, err
		}
		glog.V(2).Infof("chose program %q from possible programs %q", chosenProgram, programs)
	}

	// The design attribute is optional. If a design is specified, only one
	// program can be specified. Multiple designs cannot be specified.
	var design string
	designs, err := getAttrFromCriteria(dutTarget.GetCriteria(), designAttr)
	if err != nil {
		return nil, err
	}

	if len(designs) == 1 {
		if len(programs) != 1 {
			return nil, fmt.Errorf("if \"attr-design\" is specified, multiple \"attr-programs\" cannot be used")
		}

		design = designs[0]
	} else if len(designs) > 1 {
		return nil, fmt.Errorf("only DutCriteria with one \"attr-design\" attribute are supported, got %q", designs)
	}

	allLicenseNames, err := getAllAttrFromCriteria(dutTarget.GetCriteria(), licenseAttr)
	if err != nil {
		return nil, err
	}

	var licenses []lab.LicenseType
	for _, names := range allLicenseNames {
		if len(names) != 1 {
			return nil, fmt.Errorf("only exactly one value can be specified in \"misc-licence\" DutCriteria, got %q", names)
		}
		name := names[0]

		licenseInt, found := lab.LicenseType_value[name]
		if !found {
			return nil, fmt.Errorf("invalid LicenseType %q", name)
		}

		licence := lab.LicenseType(licenseInt)
		if licence == lab.LicenseType_LICENSE_TYPE_UNSPECIFIED {
			return nil, fmt.Errorf("LICENSE_TYPE_UNSPECIFIED not allowed")
		}

		licenses = append(licenses, licence)
	}

	var suiteInfos []*suiteInfo
	for _, suite := range rule.GetTestSuites() {
		switch spec := suite.Spec.(type) {
		case *testpb.TestSuite_TestCaseIds:
			if isVm {
				return nil, fmt.Errorf("TestCaseIdLists are only valid for HW tests")
			}
			for _, id := range spec.TestCaseIds.GetTestCaseIds() {
				suiteInfos = append(
					suiteInfos,
					&suiteInfo{
						program:      chosenProgram,
						design:       design,
						pool:         pool,
						suite:        id.Value,
						environment:  HW,
						boardVariant: boardVariant,
						licenses:     licenses,
					})
			}
		case *testpb.TestSuite_TestCaseTagCriteria_:
			if !isVm {
				return nil, fmt.Errorf("TestCaseTagCriteria are only valid for VM tests")
			}

			var env testEnvironment
			name := suite.GetName()
			switch {
			case strings.HasPrefix(name, "tast_vm"):
				env = TastVM
			case strings.HasPrefix(name, "tast_gce"):
				env = TastGCE
			default:
				return nil, fmt.Errorf("VM suite names must start with either \"tast_vm\" or \"tast_gce\" in CTP1 compatibility mode, got %q", name)
			}

			if design != "" {
				glog.Warning("attr-design DutCriteria has no effect on VM tests")
			}

			if len(licenses) > 0 {
				glog.Warning("misc-licenses DutCriteria has no effect on VM tests")
			}

			suiteInfos = append(suiteInfos,
				&suiteInfo{
					program:      chosenProgram,
					pool:         pool,
					suite:        suite.GetName(),
					tastExpr:     tagCriteriaToTastExpr(*spec.TestCaseTagCriteria),
					environment:  env,
					boardVariant: boardVariant,
				})
		default:
			return nil, fmt.Errorf("TestSuite spec type %T is not supported", spec)
		}

	}

	return suiteInfos, nil
}

// extractSuiteInfos returns a map from build target name to suiteInfos for the
// build target. There is one suiteInfo per CoverageRule in hwTestPlans and
// vmTestPlans.
func extractSuiteInfos(
	rnd *rand.Rand,
	hwTestPlans []*test_api_v1.HWTestPlan,
	vmTestPlans []*test_api_v1.VMTestPlan,
	dutAttributeList *testpb.DutAttributeList,
	boardPriorityList *testplans.BoardPriorityList,
	buildTargetToBuildInfo map[string]*buildInfo,
) (map[string][]*suiteInfo, error) {
	// Find relevant attributes in the DutAttributeList.
	var programAttr, designAttr, poolAttr, licenseAttr *testpb.DutAttribute
	for _, attr := range dutAttributeList.GetDutAttributes() {
		switch attr.Id.Value {
		case "attr-program":
			programAttr = attr
		case "attr-design":
			designAttr = attr
		case "swarming-pool":
			poolAttr = attr
		case "misc-license":
			licenseAttr = attr
		}
	}

	if programAttr == nil {
		return nil, fmt.Errorf("\"attr-program\" not found in DutAttributeList")
	}

	if poolAttr == nil {
		return nil, fmt.Errorf("\"swarming-pool\" not found in DutAttributeList")
	}

	if designAttr == nil {
		return nil, fmt.Errorf("\"attr-design\" not found in DutAttributeList")
	}

	if licenseAttr == nil {
		return nil, fmt.Errorf("\"misc-license\" not found in DutAttributeList")
	}

	buildTargetToSuiteInfos := map[string][]*suiteInfo{}
	prioritySelector := priority.NewRandomWeightedSelector(
		rnd,
		boardPriorityList,
	)

	for _, hwTestPlan := range hwTestPlans {
		for _, rule := range hwTestPlan.GetCoverageRules() {
			isVm := false
			suiteInfos, err := coverageRuleToSuiteInfo(
				rule, poolAttr, programAttr, designAttr, licenseAttr, buildTargetToBuildInfo, prioritySelector, isVm,
			)
			if err != nil {
				return nil, err
			}

			for _, info := range suiteInfos {
				buildTarget := info.getBuildTarget()
				if _, ok := buildTargetToSuiteInfos[buildTarget]; !ok {
					buildTargetToSuiteInfos[buildTarget] = []*suiteInfo{}
				}

				buildTargetToSuiteInfos[buildTarget] = append(buildTargetToSuiteInfos[buildTarget], info)
			}
		}
	}

	for _, vmTestPlan := range vmTestPlans {
		for _, rule := range vmTestPlan.GetCoverageRules() {
			isVm := true
			suiteInfos, err := coverageRuleToSuiteInfo(
				rule, poolAttr, programAttr, designAttr, licenseAttr, buildTargetToBuildInfo, prioritySelector, isVm,
			)
			if err != nil {
				return nil, err
			}

			for _, info := range suiteInfos {
				buildTarget := info.getBuildTarget()
				if _, ok := buildTargetToSuiteInfos[buildTarget]; !ok {
					buildTargetToSuiteInfos[buildTarget] = []*suiteInfo{}
				}

				buildTargetToSuiteInfos[buildTarget] = append(buildTargetToSuiteInfos[buildTarget], info)
			}
		}
	}

	return buildTargetToSuiteInfos, nil
}

// ToCTP1 converts a [VM|HW]TestPlan to a GenerateTestPlansResponse, which can
// be used with CTP1.
//
// [HW|VM]TestPlan protos target CTP2, this method is meant to provide backwards
// compatibility with CTP1. Because CTP1 does not support rules-based testing,
// there are some limitations to the [HW|VM]TestPlans that can be converted:
//
// - Both the "attr-program" and "swarming-pool" DutAttributes must be used in
// each DutTarget. The "attr-design" and "misc-license" DutAttributes are
// optional.
//
// - Multiple values for "attr-program" are allowed, a program will be chosen
// randomly proportional to the board's priority in boardPriorityList (lowest
// priority is most likely to get chosen, negative priorities are allowed,
// programs without a priority get priority 0).
//
// - Only TestCaseIds are supported for hardware testing, and only
// TestCaseTagCriteria are supported for VM testing.
//
// - generateTestPlanReq is needed to provide Build protos for the builds being
// tested.
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

	// Form a map from buildTarget to buildInfo, which will be needed by calls to
	// extractSuiteInfos.
	buildTargetToBuildInfo := map[string]*buildInfo{}
	for _, buildInfo := range buildInfos {
		buildTargetToBuildInfo[buildInfo.buildTarget] = buildInfo
	}

	buildTargetToSuiteInfos, err := extractSuiteInfos(
		rnd, hwTestPlans, vmTestPlans, dutAttributeList, boardPriorityList, buildTargetToBuildInfo,
	)
	if err != nil {
		return nil, err
	}

	var hwTestUnits []*testplans.HwTestUnit
	var vmTestUnits []*testplans.TastVmTestUnit
	var gceTestUnits []*testplans.TastGceTestUnit

	// Join the buildInfos and suiteInfos on build target name. Each build maps
	// to one HwTestUnit, each suite maps to one HwTestCfg_HwTest.
	for _, buildInfo := range buildInfos {
		suiteInfos, ok := buildTargetToSuiteInfos[buildInfo.buildTarget]
		if !ok {
			glog.Warningf("no suites found for build %q, skipping tests", buildInfo.buildTarget)
			continue
		}

		// Maps from display name, which should uniquely identify a test for a
		// given (buildTarget, model, suite) combo, to a test.
		hwTests := make(map[string]*testplans.HwTestCfg_HwTest)
		tastVMTests := make(map[string]*testplans.TastVmTestCfg_TastVmTest)
		tastGCETests := make(map[string]*testplans.TastGceTestCfg_TastGceTest)
		for _, suiteInfo := range suiteInfos {
			switch env := suiteInfo.environment; env {
			case HW:
				// If a design is set, include it in the display name
				var displayName string
				if len(suiteInfo.design) > 0 {
					displayName = fmt.Sprintf("hw.%s.%s.%s", suiteInfo.getBuildTarget(), suiteInfo.design, suiteInfo.suite)
				} else {
					displayName = fmt.Sprintf("hw.%s.%s", suiteInfo.getBuildTarget(), suiteInfo.suite)
				}
				hwTest := &testplans.HwTestCfg_HwTest{
					Suite:       suiteInfo.suite,
					SkylabBoard: suiteInfo.program,
					SkylabModel: suiteInfo.design,
					Pool:        suiteInfo.pool,
					Licenses:    suiteInfo.licenses,
					Common: &testplans.TestSuiteCommon{
						DisplayName: displayName,
						// TODO(b/218319842): Set critical value based on v2 test disablement config.
						Critical: &wrapperspb.BoolValue{
							Value: true,
						},
					},
				}

				if _, found := hwTests[displayName]; found {
					glog.V(2).Infof("HwTest already added: %q", hwTest)
				} else {
					hwTests[displayName] = hwTest
					glog.V(2).Infof("added HwTest: %q", hwTest)
				}
			case TastVM:
				displayName := fmt.Sprintf("vm.%s.%s", suiteInfo.getBuildTarget(), suiteInfo.suite)
				tastVMTest := &testplans.TastVmTestCfg_TastVmTest{
					SuiteName: suiteInfo.suite,
					TastTestExpr: []*testplans.TastVmTestCfg_TastTestExpr{
						{
							TestExpr: suiteInfo.tastExpr,
						},
					},
					Common: &testplans.TestSuiteCommon{
						DisplayName: displayName,
						Critical: &wrapperspb.BoolValue{
							Value: true,
						},
					},
				}

				if _, found := tastVMTests[displayName]; found {
					glog.V(2).Infof("TastVmTest already added: %q", tastVMTest)
				} else {
					tastVMTests[displayName] = tastVMTest
					glog.V(2).Infof("added TastVmTest %q", tastVMTest)
				}
			case TastGCE:
				displayName := fmt.Sprintf("gce.%s.%s", suiteInfo.getBuildTarget(), suiteInfo.suite)
				tastGCETest := &testplans.TastGceTestCfg_TastGceTest{
					SuiteName: suiteInfo.suite,
					TastTestExpr: []*testplans.TastGceTestCfg_TastTestExpr{
						{
							TestExpr: suiteInfo.tastExpr,
						},
					},
					GceMetadata: &testplans.TastGceTestCfg_TastGceTest_GceMetadata{
						Project:     "chromeos-gce-tests",
						Zone:        "us-central1-a",
						MachineType: "n2-standard-8",
						Network:     "chromeos-gce-tests",
						Subnet:      "us-central1",
					},
					Common: &testplans.TestSuiteCommon{
						DisplayName: displayName,
						Critical: &wrapperspb.BoolValue{
							Value: true,
						},
					},
				}

				if _, found := tastGCETests[displayName]; found {
					glog.V(2).Infof("TastGceTest already added: %q", tastGCETest)
				} else {
					tastGCETests[displayName] = tastGCETest
					glog.V(2).Infof("added TastGceTest: %q", tastGCETest)
				}
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
					HwTest: sortedValuesFromMap(hwTests),
				},
			}
			hwTestUnits = append(hwTestUnits, hwTestUnit)
		}
		if len(tastVMTests) > 0 {
			vmTestUnit := &testplans.TastVmTestUnit{
				Common: common,
				TastVmTestCfg: &testplans.TastVmTestCfg{
					TastVmTest: sortedValuesFromMap(tastVMTests),
				},
			}
			vmTestUnits = append(vmTestUnits, vmTestUnit)
		}
		if len(tastGCETests) > 0 {
			gceTestUnit := &testplans.TastGceTestUnit{
				Common: common,
				TastGceTestCfg: &testplans.TastGceTestCfg{
					TastGceTest: sortedValuesFromMap(tastGCETests),
				},
			}
			gceTestUnits = append(gceTestUnits, gceTestUnit)
		}

	}

	return &testplans.GenerateTestPlanResponse{
		HwTestUnits:           hwTestUnits,
		DirectTastVmTestUnits: vmTestUnits,
		TastGceTestUnits:      gceTestUnits,
	}, nil
}
