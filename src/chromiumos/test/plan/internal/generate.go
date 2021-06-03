// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"context"
	"errors"

	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/chromiumos/config/go/test/plan"
)

// Generate computes CoverageRules based on SourceTestPlans.
//
// sourceTestPlans must be non-empty. buildSummaryList and dutAttributeList must
// be non-nil.
func Generate(
	ctx context.Context, sourceTestPlans []*plan.SourceTestPlan,
	buildSummaryList *buildpb.SystemImage_BuildSummaryList,
	dutAttributeList *testpb.DutAttributeList,
) ([]*testpb.CoverageRule, error) {
	return nil, errors.New("generate not implemented")
}
