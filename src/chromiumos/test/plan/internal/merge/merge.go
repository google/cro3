// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package merge

import (
	"sort"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/chromiumos/config/go/test/plan"
	"go.chromium.org/luci/common/data/stringset"
)

// dedupTestEnvironments returns a copy of envs with duplicates removed.
func dedupTestEnvironments(envs []plan.SourceTestPlan_TestEnvironment) []plan.SourceTestPlan_TestEnvironment {
	envsMap := make(map[plan.SourceTestPlan_TestEnvironment]bool)
	for _, env := range envs {
		envsMap[env] = true
	}

	output := make([]plan.SourceTestPlan_TestEnvironment, 0, len(envsMap))
	for env := range envsMap {
		output = append(output, env)
	}

	sort.Slice(output, func(i, j int) bool {
		return output[i] < output[j]
	})

	return output
}

// SourceTestPlans merges multiple SourceTestPlans into a single
// SourceTestPlan.
//
// Merging behavior:
// - The output enabled_test_environments is the union of all input
//   enabled_test_environments. For example, if one input SourceTestPlan has
//   HARDWARE enabled, and another has VIRTUAL, both HARDWARE and VIRTUAL are
//   enabled on the output.
//
// - path_regexps and path_regexp_excludes are not set on the output. Since the
//   input SourceTestPlans are potentially coming from different projects,
//   combining these fields does not make sense. The determination of whether
//   a SourceTestPlan is relevant should be done before merging.
//
// - The output test_tags and test_tag_excludes are the union of all input
//   test_tags and test_tag_excludes. In the case that one input SourceTestPlan
//   has a test_tag that another input SourceTestPlan has as a
//   test_tag_excludes, the tag is in the output test_tags, and not in the
//   output test_tag_excludes; i.e. input test_tags take precedence over input
//   test_tag_excludes.
//
// - Requirements, such as the kernel_versions field, are output as the union of
//   all input requirements. For example, if one input SourceTestPlan has
//   kernel_versions set, and another has soc_families, both kernel_versions and
//   soc_families are enabled on the output.
func SourceTestPlans(plans ...*plan.SourceTestPlan) *plan.SourceTestPlan {
	output := &plan.SourceTestPlan{}

	// proto.Merge implements most of the required behavior. Cleanups on
	// EnabledTestEnvironments, PathRegexps, and TestTags are done after.
	for _, plan := range plans {
		proto.Merge(output, plan)
	}

	output.EnabledTestEnvironments = dedupTestEnvironments(output.GetEnabledTestEnvironments())

	// Clear PathRegexps(Excludes)
	output.PathRegexps = nil
	output.PathRegexpExcludes = nil

	// Dedup TestTags
	output.TestTags = stringset.NewFromSlice(output.GetTestTags()...).ToSlice()

	// Dedup TestTagExcludes and remove any tag in TestTags
	testTagExcludes := stringset.NewFromSlice(output.GetTestTagExcludes()...)
	testTagExcludes.DelAll(output.GetTestTags())
	output.TestTagExcludes = testTagExcludes.ToSlice()

	return output
}
