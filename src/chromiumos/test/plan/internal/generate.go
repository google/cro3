// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package testplan contains the main application code for the testplan tool.
package testplan

import (
	"errors"

	"github.com/golang/glog"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/chromiumos/config/go/test/plan"

	"chromiumos/test/plan/internal/coveragerules"
	"chromiumos/test/plan/internal/merge"
)

// Generate computes CoverageRules based on SourceTestPlans.
//
// sourceTestPlans must be non-empty. buildSummaryList and dutAttributeList must
// be non-nil.
func Generate(
	sourceTestPlans []*plan.SourceTestPlan,
	buildSummaryList *buildpb.SystemImage_BuildSummaryList,
	dutAttributeList *testpb.DutAttributeList,
) ([]*testpb.CoverageRule, error) {
	if len(sourceTestPlans) == 0 {
		return nil, errors.New("sourceTestPlans must be non-empty")
	}

	if buildSummaryList == nil {
		return nil, errors.New("buildSummaryList must be non-nil")
	}

	if dutAttributeList == nil {
		return nil, errors.New("dutAttributeList must be non-nil")
	}

	for _, plan := range sourceTestPlans {
		if len(plan.PathRegexps) > 0 || len(plan.PathRegexpExcludes) > 0 {
			return nil, errors.New("SourceTestPlans passed to generate should not set path_regexps")
		}
	}

	mergedSourceTestPlan := merge.SourceTestPlans(sourceTestPlans...)

	glog.Infof("Merged %d SourceTestPlans together", len(sourceTestPlans))
	glog.V(1).Infof("Merged SourceTestPlan: %s", mergedSourceTestPlan)

	return coveragerules.Generate(
		mergedSourceTestPlan, buildSummaryList, dutAttributeList,
	)
}
