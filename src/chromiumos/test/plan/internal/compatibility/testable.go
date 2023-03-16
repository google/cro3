// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package compatibility

import (
	"fmt"

	testpb "go.chromium.org/chromiumos/config/go/test/api"
	test_api_v1 "go.chromium.org/chromiumos/config/go/test/api/v1"
	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"
	bbpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/data/stringset"
)

// buildCouldMatchCoverageRule returns whether bi could possibly match rule.
// This is true iff:
//
//  1. bi.buildTarget matches a program in rule. If rule has set a board variant,
//     the match checks bi.buildTarget against <program>-<variant>.
//
//  2. bi.profile matches the profile in rule (both can possibly be empty).
func buildCouldMatchCoverageRule(bi *buildInfo, rule *testpb.CoverageRule, programAttr *testpb.DutAttribute) (bool, error) {
	if len(rule.GetDutTargets()) != 1 {
		return false, fmt.Errorf("expected exactly one DutTarget in CoverageRule, got %q", rule)
	}

	dutTarget := rule.GetDutTargets()[0]

	programs, err := getAttrFromCriteria(dutTarget.GetCriteria(), programAttr)
	if err != nil {
		return false, err
	}

	// If board variant is set in the ProvisionConfig, match the bi.buildTarget
	// against <program>-<variant> instead of just program. programs is still
	// pointing to the slice in the CoverageRule, so create a new slice with
	// the variant added instead of modifying the slice in the CoverageRule.
	provisionConfig := dutTarget.GetProvisionConfig()
	if len(provisionConfig.GetBoardVariant()) > 0 {
		programsWithVariant := []string{}
		for _, program := range programs {
			programsWithVariant = append(programsWithVariant, program+"-"+provisionConfig.GetBoardVariant())
		}

		if !stringset.NewFromSlice(programsWithVariant...).Has(bi.buildTarget) {
			return false, nil
		}
	} else {
		if !stringset.NewFromSlice(programs...).Has(bi.buildTarget) {
			return false, nil
		}
	}

	// Build targets match, return true iff profiles match.
	return bi.profile == dutTarget.GetProvisionConfig().GetProfile(), nil
}

// TestableBuilds computes the builds in generateTestPlanReq that could possibly
// match a CoverageRule in hwTestPlans or vmTestPlans. A build can match a
// CoverageRule if its target matches the target(s), variant, and profile
// required by the CoverageRule. The builds in generateTestPlanReq do not
// necessarily need to be completed with test artifacts, they just need to have
// build target information set on the input property. TestableBuilds is
// different from ToCTP1, which actually selects specific builds and programs to
// test based off completed builds; TestableBuilds computes which builds could
// possibly be tested, e.g. to know which builds to collect.
func TestableBuilds(
	hwTestPlans []*test_api_v1.HWTestPlan,
	vmTestPlans []*test_api_v1.VMTestPlan,
	builds []*bbpb.Build,
	builderConfigs *chromiumos.BuilderConfigs,
	dutAttributeList *testpb.DutAttributeList,
) ([]*bbpb.Build, error) {
	// Extract the build protos into buildInfos, including builds that don't have
	// test artifacts (builds aren't necessarily completed yet).
	buildInfos, err := buildsToBuildInfos(builds, builderConfigs, false)
	if err != nil {
		return nil, err
	}

	programAttr, err := getDutAttribute(dutAttributeList, "attr-program")
	if err != nil {
		return nil, err
	}

	allCoverageRules := make([]*testpb.CoverageRule, 0)
	for _, plan := range hwTestPlans {
		allCoverageRules = append(allCoverageRules, plan.GetCoverageRules()...)
	}

	for _, plan := range vmTestPlans {
		allCoverageRules = append(allCoverageRules, plan.GetCoverageRules()...)
	}

	testableBuilds := make([]*bbpb.Build, 0)

CheckBuild:
	for _, buildInfo := range buildInfos {
		for _, rule := range allCoverageRules {
			couldMatch, err := buildCouldMatchCoverageRule(buildInfo, rule, programAttr)
			if err != nil {
				return nil, err
			}

			if couldMatch {
				testableBuilds = append(testableBuilds, buildInfo.build)
				continue CheckBuild
			}
		}
	}

	return testableBuilds, nil
}
