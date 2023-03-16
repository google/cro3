// Package compatibility provides functions for backwards compatiblity with
// test platform.
//
// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package compatibility

import (
	"errors"
	"fmt"
	"math/rand"
	"sort"
	"strings"

	"chromiumos/test/plan/internal/compatibility/priority"

	"github.com/golang/glog"
	"github.com/golang/protobuf/proto"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	test_api_v1 "go.chromium.org/chromiumos/config/go/test/api/v1"
	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"
	"go.chromium.org/chromiumos/infra/proto/go/lab"
	"go.chromium.org/chromiumos/infra/proto/go/testplans"
	bbpb "go.chromium.org/luci/buildbucket/proto"
	"google.golang.org/protobuf/types/known/structpb"
	"google.golang.org/protobuf/types/known/wrapperspb"
)

// criterionMatchesAttribute returns true if criterion's AttributeId matches
// attr's Id or any of attr's Aliases.
func criterionMatchesAttribute(criterion *testpb.DutCriterion, attr *testpb.DutAttribute) bool {
	if criterion.GetAttributeId().GetValue() == attr.GetId().GetValue() {
		return true
	}
	for _, alias := range attr.GetAliases() {
		if criterion.GetAttributeId().GetValue() == alias {
			return true
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
// 1. Choose a program with a critical completed build. If there are multiple
// programs, choose with prioritySelector.
//
// 2. Choose a program with a non-critical completed build. If there are
// multiple programs, choose with prioritySelector.
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
		value, ok = s.GetFields()[field]
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

// buildInfo describes properties parsed from a Buildbucket build and
// BuilderConfigs.
type buildInfo struct {
	// the build_target.name input property.
	buildTarget string

	// the builder.builder field.
	builderName string

	// the build.portage_profile.profile field from the BuilderConfig. If the
	// build didn't have a corresponding BuilderConfig, this will be empty.
	profile string

	// the critical field.
	criticality bbpb.Trinary

	// a payload containing information about the build's artifacts. If the
	// build doesn't have testable artifacts, this will be nil.
	payload *testplans.BuildPayload

	// a pointer to the Build itself, useful for functions that need the above
	// extracted fields for computation, but still return results containing
	// the actual Build.
	build *bbpb.Build
}

// getTestArtifacts returns a BuildPayload pointing to the test artifacts in
// build. If the build doesn't contain test artifacts, nil is returned.
func getTestArtifacts(build *bbpb.Build) (*testplans.BuildPayload, error) {
	builderName := build.GetBuilder().GetBuilder()

	filesByArtifact, ok := extractFromProtoStruct(
		build.GetOutput().GetProperties(),
		"artifacts", "files_by_artifact",
	)
	if !ok {
		glog.Warningf("artifacts.files_by_artifact not found in output properties of build %q", builderName)
		return nil, nil
	}

	if filesByArtifact.GetStructValue() == nil {
		return nil, fmt.Errorf("artifacts.files_by_artifact must be a non-empty struct")
	}

	// The presence of any one of these artifacts is enough to tell us that this
	// build should be considered for testing. It is possible they are present
	// as keys in the map but empty lists; in this case, skip the artifact
	// and log a warning, as this is somewhat unexpected.
	testArtifacts := []string{
		"AUTOTEST_FILES",
		"IMAGE_ZIP",
		"PINNED_GUEST_IMAGES",
		"TAST_FILES",
		"TEST_UPDATE_PAYLOAD",
	}

	foundTestArtifact := false
	for _, testArtifact := range testArtifacts {
		files, found := filesByArtifact.GetStructValue().GetFields()[testArtifact]
		if found {
			// The key exists in the map, check that it is a non-empty list.
			switch files.GetKind().(type) {
			case *structpb.Value_ListValue:
				if len(files.GetListValue().GetValues()) > 0 {
					glog.Infof(
						"found test artifact %q on build %q",
						testArtifact,
						builderName,
					)
					foundTestArtifact = true
					break
				}

				glog.Warningf(
					"test artifact %q is present but empty on build %q",
					testArtifact,
					builderName,
				)
			default:
				glog.Warningf(
					"test artifact %q is present but not a list, this is unexpected. On build %q. value is: %q",
					testArtifact,
					builderName,
					files,
				)
			}
		}
	}

	if !foundTestArtifact {
		glog.Warningf("no test artifacts found for build %q", builderName)
		return nil, nil
	}

	// If files_by_artifact was populated with test artifacts, but the GS fields
	// are missing, return an error.
	artifactsGsBucket, ok := extractStringFromProtoStruct(
		build.GetOutput().GetProperties(),
		"artifacts", "gs_bucket",
	)
	if !ok {
		return nil, fmt.Errorf("artifacts.gs_bucket not found for build %q", builderName)
	}

	artifactsGsPath, ok := extractStringFromProtoStruct(
		build.GetOutput().GetProperties(),
		"artifacts", "gs_path",
	)
	if !ok {
		return nil, fmt.Errorf("artifacts.gs_path not found for build %q", builderName)
	}

	return &testplans.BuildPayload{
		ArtifactsGsBucket: artifactsGsBucket,
		ArtifactsGsPath:   artifactsGsPath,
		FilesByArtifact:   filesByArtifact.GetStructValue(),
	}, nil

}

// buildsToBuildInfos extracts properties from builds into buildInfos. If
// skipIfNoTestArtifacts is true, builds without test artifacts will not be
// returned. Builds that have set the pointless_build output property are always
// skipped.
func buildsToBuildInfos(
	builds []*bbpb.Build,
	builderConfigs *chromiumos.BuilderConfigs,
	skipIfNoTestArtifacts bool,
) ([]*buildInfo, error) {
	builderToBuilderConfig := make(map[string]*chromiumos.BuilderConfig)
	for _, builder := range builderConfigs.GetBuilderConfigs() {
		builderToBuilderConfig[builder.GetId().GetName()] = builder
	}

	buildInfos := []*buildInfo{}

	for _, build := range builds {
		builderName := build.GetBuilder().GetBuilder()

		pointless, ok := extractFromProtoStruct(build.GetOutput().GetProperties(), "pointless_build")
		if ok && pointless.GetBoolValue() {
			glog.Warningf("build %q is pointless, skipping", builderName)
			continue
		}

		buildTarget, ok := extractStringFromProtoStruct(
			build.GetInput().GetProperties(),
			"build_target", "name",
		)
		if !ok {
			glog.Warningf("build_target.name not found in input properties of build %q, skipping", builderName)
			continue
		}

		payload, err := getTestArtifacts(build)
		if err != nil {
			return nil, err
		}

		if payload == nil && skipIfNoTestArtifacts {
			glog.Warningf("skipIfNoTestArtifacts set, skipping build %q", builderName)
		}

		// Attempt to lookup the BuilderConfig to find profile information. If
		// no BuilderConfig is found, keep the profile empty and log a warning,
		// this build will match against CoverageRules that don't specify a
		// profile.
		profile := ""
		builderConfig, ok := builderToBuilderConfig[builderName]
		if ok {
			profile = builderConfig.GetBuild().GetPortageProfile().GetProfile()
		} else {
			glog.Warningf("no BuilderConfig found for %q", builderName)
		}

		buildInfos = append(buildInfos, &buildInfo{
			buildTarget: buildTarget,
			builderName: build.GetBuilder().GetBuilder(),
			profile:     profile,
			criticality: build.GetCritical(),
			payload:     payload,
			build:       build,
		},
		)
	}

	return buildInfos, nil
}

// Defines the environment a test should run in, e.g. hardware, Tast on VM, Tast
// on GCE.
type testEnvironment int64

const (
	undefined testEnvironment = iota
	hw
	tastVM
	tastGCE
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
	// optional, tagCriteria that define the suite. Only valid if runViaCft is
	// set. If not set, the name of the suite is used as the id to lookup and
	// execute the suite.
	tagCriteria *testpb.TestSuite_TestCaseTagCriteria
	// whether the test suite is critical or not
	critical bool
	// optional, variant of the build target to test. For example, if program
	// is "coral" and boardVariant is "kernelnext", the "coral-kernelnext" build
	// will be used.
	boardVariant string
	// optional, profile of the build target to test. For example "asan".
	profile string
	// optional, the licenses required for the DUT the test will run on.
	licenses []lab.LicenseType
	// optional, the total number of shards to be used in a test run. Only valid
	// if environment is TastVM or TastGCE.
	totalShards int64
	// optional, if true then run test suites in this rule via CFT workflow.
	runViaCft bool
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

// getTastExpr converts suiteInfo's TestCaseTagCriteria to a Tast expression.
// All of the included and excluded tags are joined together with " && ", i.e.
// Tast expressions with "|" cannot be generated. Excluded tags are negated with
// "!". The entire expression is surrounded in parens.
//
// See https://chromium.googlesource.com/chromiumos/platform/tast/+/HEAD/docs/running_tests.md
// for a description of Tast expressions.
func (si *suiteInfo) getTastExpr() string {
	attributes := si.tagCriteria.GetTags()
	for _, tag := range si.tagCriteria.GetTagExcludes() {
		attributes = append(attributes, "!"+tag)
	}

	return "(" + strings.Join(attributes, " && ") + ")"
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
	isVM bool,
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

	// For simplicitly, only allow a board variant or profile to be specified if
	// a single program is specified. I.e. a rule that specifies it wants to
	// test the "kernelnext" or "asan" build chosen from multiple programs is
	// not currently supported.
	var chosenProgram string
	boardVariant := dutTarget.GetProvisionConfig().GetBoardVariant()
	profile := dutTarget.GetProvisionConfig().GetProfile()
	if len(boardVariant) > 0 || len(profile) > 0 {
		if len(programs) != 1 {
			return nil, fmt.Errorf(
				"board_variant (%q) and profile (%q) cannot be specified if multiple programs (%q) are specified",
				boardVariant, profile, programs,
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

	ruleCritical := true
	if rule.Critical != nil {
		ruleCritical = rule.GetCritical().GetValue()
		glog.V(2).Infof("rule %q explicitly sets criticality %v", rule.GetName(), ruleCritical)
	}

	var buildTarget string
	if len(boardVariant) > 0 {
		buildTarget = fmt.Sprintf("%s-%s", chosenProgram, boardVariant)
	} else {
		buildTarget = chosenProgram
	}

	programCritical := true
	buildInfo, found := buildTargetToBuildInfo[buildTarget]
	if found && buildInfo.criticality != bbpb.Trinary_YES {
		programCritical = false
		glog.V(2).Infof("build target %q explicitly sets criticality %q", buildTarget, buildInfo.criticality)
	}

	// The rule and program must both be critical in order for it to be blocking
	// in CQ.
	critical := ruleCritical && programCritical

	var suiteInfos []*suiteInfo
	for _, suite := range rule.GetTestSuites() {
		switch spec := suite.Spec.(type) {
		case *testpb.TestSuite_TestCaseIds:
			if isVM {
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
						tagCriteria:  nil,
						environment:  hw,
						critical:     critical,
						boardVariant: boardVariant,
						profile:      profile,
						licenses:     licenses,
						runViaCft:    rule.RunViaCft,
					})
			}
		case *testpb.TestSuite_TestCaseTagCriteria_:
			var env testEnvironment
			if isVM {
				name := suite.GetName()
				switch {
				case strings.HasPrefix(name, "tast_vm"):
					env = tastVM
				case strings.HasPrefix(name, "tast_gce"):
					env = tastGCE
				default:
					return nil, fmt.Errorf("VM suite names must start with either \"tast_vm\" or \"tast_gce\" in CTP1 compatibility mode, got %q", name)
				}
			} else {
				env = hw
			}

			suiteInfos = append(suiteInfos,
				&suiteInfo{
					program:      chosenProgram,
					design:       design,
					pool:         pool,
					suite:        suite.GetName(),
					tagCriteria:  suite.GetTestCaseTagCriteria(),
					environment:  env,
					critical:     critical,
					boardVariant: boardVariant,
					profile:      profile,
					totalShards:  suite.GetTotalShards(),
					licenses:     licenses,
					runViaCft:    rule.GetRunViaCft(),
				})
		default:
			return nil, fmt.Errorf("TestSuite spec type %T is not supported", spec)
		}

	}

	return suiteInfos, nil
}

// getDutAttribute returns the DutAttribute matching id from dutAttributeList.
// If no matching DutAttribute is found, returns an error.
func getDutAttribute(dutAttributeList *testpb.DutAttributeList, id string) (*testpb.DutAttribute, error) {
	for _, attr := range dutAttributeList.GetDutAttributes() {
		if attr.GetId().GetValue() == id {
			return attr, nil
		}
	}

	return nil, fmt.Errorf("%q not found in DutAttributeList", id)
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
	programAttr, err := getDutAttribute(dutAttributeList, "attr-program")
	if err != nil {
		return nil, err
	}

	designAttr, err := getDutAttribute(dutAttributeList, "attr-design")
	if err != nil {
		return nil, err
	}

	poolAttr, err := getDutAttribute(dutAttributeList, "swarming-pool")
	if err != nil {
		return nil, err
	}

	licenseAttr, err := getDutAttribute(dutAttributeList, "misc-license")
	if err != nil {
		return nil, err
	}

	buildTargetToSuiteInfos := map[string][]*suiteInfo{}
	prioritySelector := priority.NewRandomWeightedSelector(
		rnd,
		boardPriorityList,
	)

	for _, hwTestPlan := range hwTestPlans {
		for _, rule := range hwTestPlan.GetCoverageRules() {
			isVM := false
			suiteInfos, err := coverageRuleToSuiteInfo(
				rule, poolAttr, programAttr, designAttr, licenseAttr, buildTargetToBuildInfo, prioritySelector, isVM,
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
			isVM := true
			suiteInfos, err := coverageRuleToSuiteInfo(
				rule, poolAttr, programAttr, designAttr, licenseAttr, buildTargetToBuildInfo, prioritySelector, isVM,
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

// createTastVMTest creates a TastVmTestCfg_TastVmTest based on a suiteInfo
// and shardIndex. Note that shardIndex is 0-based.
func createTastVMTest(buildInfo *buildInfo, suiteInfo *suiteInfo, shardIndex int64) (*testplans.TastVmTestCfg_TastVmTest, error) {
	if suiteInfo.totalShards != 0 && shardIndex > suiteInfo.totalShards {
		return nil, fmt.Errorf("shardIndex cannot be greater than suiteInfo.totalShards")
	}
	// If the suite is configured to run more than one shard, include that info in the display name
	var displayName string
	if suiteInfo.totalShards > 1 {
		// shardIndex is 0-based, but we use 1-based indexing for the display name.
		displayName = fmt.Sprintf("%s.tast_vm.%s_shard_%d_of_%d", buildInfo.builderName, suiteInfo.suite, shardIndex+1, suiteInfo.totalShards)
	} else {
		displayName = fmt.Sprintf("%s.tast_vm.%s", buildInfo.builderName, suiteInfo.suite)
	}
	tastVMTest := &testplans.TastVmTestCfg_TastVmTest{
		SuiteName: suiteInfo.suite,
		TastTestExpr: []*testplans.TastVmTestCfg_TastTestExpr{
			{
				TestExpr: suiteInfo.getTastExpr(),
			},
		},
		Common: &testplans.TestSuiteCommon{
			DisplayName: displayName,
			Critical: &wrapperspb.BoolValue{
				Value: suiteInfo.critical,
			},
		},
	}
	if suiteInfo.totalShards > 1 {
		tastVMTest.TastTestShard = &testplans.TastTestShard{
			TotalShards: suiteInfo.totalShards,
			ShardIndex:  shardIndex,
		}
	}
	return tastVMTest, nil
}

// createTastGCETest creates a TastGceTestCfg_TastGceTest based on a suiteInfo
// and shardIndex. Note that shardIndex is 0-based.
func createTastGCETest(buildInfo *buildInfo, suiteInfo *suiteInfo, shardIndex int64) (*testplans.TastGceTestCfg_TastGceTest, error) {
	if suiteInfo.totalShards != 0 && shardIndex > suiteInfo.totalShards {
		return nil, fmt.Errorf("shardIndex cannot be greater than suiteInfo.totalShards")
	}
	// If the suite is configured to run more than one shard, include that info in the display name
	var displayName string
	if suiteInfo.totalShards > 1 {
		// shardIndex is 0-based, but we use 1-based indexing for the display name.
		displayName = fmt.Sprintf("%s.tast_gce.%s_shard_%d_of_%d", buildInfo.builderName, suiteInfo.suite, shardIndex+1, suiteInfo.totalShards)
	} else {
		displayName = fmt.Sprintf("%s.tast_gce.%s", buildInfo.builderName, suiteInfo.suite)
	}
	tastGCETest := &testplans.TastGceTestCfg_TastGceTest{
		SuiteName: suiteInfo.suite,
		TastTestExpr: []*testplans.TastGceTestCfg_TastTestExpr{
			{
				TestExpr: suiteInfo.getTastExpr(),
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
				Value: suiteInfo.critical,
			},
		},
	}
	if suiteInfo.totalShards > 1 {
		tastGCETest.TastTestShard = &testplans.TastTestShard{
			TotalShards: suiteInfo.totalShards,
			ShardIndex:  shardIndex,
		}
	}
	return tastGCETest, nil
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
//
// - builderConfigs is needed to provide Portage profile information for the
// builds being tested.
func ToCTP1(
	rnd *rand.Rand,
	hwTestPlans []*test_api_v1.HWTestPlan,
	vmTestPlans []*test_api_v1.VMTestPlan,
	generateTestPlanReq *testplans.GenerateTestPlanRequest,
	dutAttributeList *testpb.DutAttributeList,
	boardPriorityList *testplans.BoardPriorityList,
	builderConfigs *chromiumos.BuilderConfigs,
) (*testplans.GenerateTestPlanResponse, error) {
	builds := make([]*bbpb.Build, 0, len(generateTestPlanReq.GetBuildbucketProtos()))
	for _, protoBytes := range generateTestPlanReq.GetBuildbucketProtos() {
		build := &bbpb.Build{}
		if err := proto.Unmarshal(protoBytes.GetSerializedProto(), build); err != nil {
			return nil, err
		}

		builds = append(builds, build)
	}

	buildInfos, err := buildsToBuildInfos(builds, builderConfigs, true)
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
			// If the build's profile doesn't match the suite's profile, skip
			// the suite. Note that majority of builds and suites don't specify
			// a profile, so they should match on the empty string.
			if buildInfo.profile != suiteInfo.profile {
				glog.Infof(
					"profile for build %q (%q) doesn't match profile for suite %q (%q), skipping",
					buildInfo.builderName, buildInfo.profile, suiteInfo.suite, suiteInfo.profile,
				)
				continue
			}

			switch env := suiteInfo.environment; env {
			case hw:
				// If a design is set, include it in the display name
				var displayName string
				if len(suiteInfo.design) > 0 {
					displayName = fmt.Sprintf("%s.%s.hw.%s", buildInfo.builderName, suiteInfo.design, suiteInfo.suite)
				} else {
					displayName = fmt.Sprintf("%s.hw.%s", buildInfo.builderName, suiteInfo.suite)
				}
				hwTest := &testplans.HwTestCfg_HwTest{
					Suite:       suiteInfo.suite,
					SkylabBoard: suiteInfo.program,
					SkylabModel: suiteInfo.design,
					Pool:        suiteInfo.pool,
					Licenses:    suiteInfo.licenses,
					Common: &testplans.TestSuiteCommon{
						DisplayName: displayName,
						Critical: &wrapperspb.BoolValue{
							Value: suiteInfo.critical,
						},
					},
					RunViaCft:   suiteInfo.runViaCft,
					TagCriteria: suiteInfo.tagCriteria,
				}

				if _, found := hwTests[displayName]; found {
					glog.V(2).Infof("HwTest already added: %q", hwTest)
				} else {
					hwTests[displayName] = hwTest
					glog.V(2).Infof("added HwTest: %q", hwTest)
				}
			case tastVM:
				if suiteInfo.totalShards > 0 {
					var i int64
					for i = 0; i < suiteInfo.totalShards; i++ {
						tastVMTest, err := createTastVMTest(buildInfo, suiteInfo, i)
						if err != nil {
							return nil, err
						}

						displayName := tastVMTest.GetCommon().GetDisplayName()
						if _, found := tastVMTests[displayName]; found {
							glog.V(2).Infof("TastVmTest already added: %q", tastVMTest)
						} else {
							tastVMTests[displayName] = tastVMTest
							glog.V(2).Infof("added TastVmTest %q", tastVMTest)
						}
					}
				} else {
					tastVMTest, err := createTastVMTest(buildInfo, suiteInfo, 0)
					if err != nil {
						return nil, err
					}

					displayName := tastVMTest.GetCommon().GetDisplayName()
					if _, found := tastVMTests[displayName]; found {
						glog.V(2).Infof("TastVmTest already added: %q", tastVMTest)
					} else {
						tastVMTests[displayName] = tastVMTest
						glog.V(2).Infof("added TastVmTest %q", tastVMTest)
					}
				}
			case tastGCE:
				if suiteInfo.totalShards > 0 {
					var i int64
					for i = 0; i < suiteInfo.totalShards; i++ {
						tastGCETest, err := createTastGCETest(buildInfo, suiteInfo, i)
						if err != nil {
							return nil, err
						}

						displayName := tastGCETest.GetCommon().GetDisplayName()
						if _, found := tastGCETests[displayName]; found {
							glog.V(2).Infof("TastGceTest already added: %q", tastGCETest)
						} else {
							tastGCETests[displayName] = tastGCETest
							glog.V(2).Infof("added TastGceTest %q", tastGCETest)
						}
					}
				} else {
					tastGCETest, err := createTastGCETest(buildInfo, suiteInfo, 0)
					if err != nil {
						return nil, err
					}

					displayName := tastGCETest.GetCommon().GetDisplayName()
					if _, found := tastGCETests[displayName]; found {
						glog.V(2).Infof("TastGceTest already added: %q", tastGCETest)
					} else {
						tastGCETests[displayName] = tastGCETest
						glog.V(2).Infof("added TastGceTest %q", tastGCETest)
					}
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
