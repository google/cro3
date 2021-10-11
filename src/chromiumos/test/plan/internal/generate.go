// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package testplan contains the main application code for the testplan tool.
package testplan

import (
	"errors"

	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/payload"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	planv1 "go.chromium.org/chromiumos/config/go/test/api/v1"
)

// Generate evals the Starlark files in planFilenames to produce a list of
// HWTestPlans.
//
// planFilenames must be non-empty. buildMetadataList, dutAttributeList, and
// flatConfigList must be non-nil.
func Generate(
	planFilenames []string,
	buildMetadataList *buildpb.SystemImage_BuildMetadataList,
	dutAttributeList *testpb.DutAttributeList,
	flatConfigList *payload.FlatConfigList,
) ([]*planv1.HWTestPlan, error) {
	if len(planFilenames) == 0 {
		return nil, errors.New("planFilenames must be non-empty")
	}

	if buildMetadataList == nil {
		return nil, errors.New("buildMetadataList must be non-nil")
	}

	if dutAttributeList == nil {
		return nil, errors.New("dutAttributeList must be non-nil")
	}

	if flatConfigList == nil {
		return nil, errors.New("flatConfigList must be non-nil")
	}

	return nil, errors.New("Generate not implemented")
}
