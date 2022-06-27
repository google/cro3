// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package testplan contains the main application code for the testplan tool.
package testplan

import (
	"context"
	"errors"

	"chromiumos/test/plan/internal/starlark"

	"github.com/golang/glog"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/payload"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	test_api_v1 "go.chromium.org/chromiumos/config/go/test/api/v1"
)

// Generate evals the Starlark files in planFilenames to produce a list of
// HWTestPlans and VMTestPlans.
//
// planFilenames must be non-empty. buildMetadataList, dutAttributeList, and
// configBundleList must be non-nil.
func Generate(
	ctx context.Context,
	planFilenames []string,
	buildMetadataList *buildpb.SystemImage_BuildMetadataList,
	dutAttributeList *testpb.DutAttributeList,
	configBundleList *payload.ConfigBundleList,
) ([]*test_api_v1.HWTestPlan, []*test_api_v1.VMTestPlan, error) {
	if len(planFilenames) == 0 {
		return nil, nil, errors.New("planFilenames must be non-empty")
	}

	if buildMetadataList == nil {
		return nil, nil, errors.New("buildMetadataList must be non-nil")
	}

	if dutAttributeList == nil {
		return nil, nil, errors.New("dutAttributeList must be non-nil")
	}

	if configBundleList == nil {
		return nil, nil, errors.New("configBundleList must be non-nil")
	}

	var allHwTestPlans []*test_api_v1.HWTestPlan
	var allVmTestPlans []*test_api_v1.VMTestPlan
	for _, planFilename := range planFilenames {
		hwTestPlans, vmTestPlans, err := starlark.ExecTestPlan(ctx, planFilename, buildMetadataList, configBundleList)
		if err != nil {
			return nil, nil, err
		}

		if len(hwTestPlans) == 0 && len(vmTestPlans) == 0 {
			glog.Warningf("starlark file %q returned no TestPlans", planFilename)
		}

		allHwTestPlans = append(allHwTestPlans, hwTestPlans...)
		allVmTestPlans = append(allVmTestPlans, vmTestPlans...)
	}

	return allHwTestPlans, allVmTestPlans, nil
}
