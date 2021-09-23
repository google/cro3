// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package coveragerules

import (
	"fmt"
	"strings"

	"github.com/golang/glog"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/payload"
)

// flatConfigWrapper provides methods helpful when reading a FlatConfigList.
type flatConfigWrapper struct {
	flatConfigList *payload.FlatConfigList
}

func newFlatConfigWrapper(flatConfigList *payload.FlatConfigList) *flatConfigWrapper {
	return &flatConfigWrapper{flatConfigList: flatConfigList}
}

// flatConfigAndBuildMetadata groups a FlatConfig and BuildMetadata that share
// the same Portage overlay and profile.
type flatConfigAndBuildMetadata struct {
	*payload.FlatConfig
	*buildpb.SystemImage_BuildMetadata
}

// joinWithBuildMetadata returns a list of flatConfigAndBuildMetadata by joining
// the FlatConfigList and a BuildMetadataList by Portage overlay and profile.
func (w *flatConfigWrapper) joinWithBuildMetadata(
	buildMetadataList *buildpb.SystemImage_BuildMetadataList,
) ([]flatConfigAndBuildMetadata, error) {
	// Build a map from Portage overlay and profile to unique BuildMetadata for
	// this key.
	type overlayProfileKey struct {
		overlay, profile string
	}

	buildTargetToMetadata := map[overlayProfileKey]*buildpb.SystemImage_BuildMetadata{}

	for _, buildMetadata := range buildMetadataList.Values {
		buildTarget := buildMetadata.GetBuildTarget().GetPortageBuildTarget()
		overlay := buildTarget.GetOverlayName()

		if overlay == "" {
			return nil, fmt.Errorf("no overlay found in BuildMetadata %v", buildMetadata)
		}

		key := overlayProfileKey{
			overlay: strings.ToLower(overlay),
			profile: strings.ToLower(buildTarget.GetProfileName()),
		}

		if _, found := buildTargetToMetadata[key]; found {
			return nil, fmt.Errorf("multiple BuildMetadatas for key %v", key)
		}

		buildTargetToMetadata[key] = buildMetadata
	}

	joinedList := []flatConfigAndBuildMetadata{}

	// For each FlatConfig, find the corresponding BuildMetadata based on
	// Portage overlay and profile.
	for _, flatConfig := range w.flatConfigList.Values {
		buildTarget := flatConfig.GetSwConfig().GetSystemBuildTarget().GetPortageBuildTarget()
		overlay := buildTarget.GetOverlayName()

		// The PortageBuildTarget may not be filled in for FlatConfigs. Fall
		// back to the program name.
		if overlay == "" {
			overlay = flatConfig.GetProgram().GetName()
		}

		key := overlayProfileKey{
			overlay: strings.ToLower(overlay),
			profile: strings.ToLower(buildTarget.GetProfileName()),
		}

		// Some FlatConfigs may not have a corresponding BuildMetadata. This is
		// common enough we log a warning instead of returning an error.
		buildMetadata, found := buildTargetToMetadata[key]
		if !found {
			glog.Warningf("no BuildMetadata for key %v", key)
			continue
		}

		joinedList = append(joinedList, flatConfigAndBuildMetadata{
			flatConfig, buildMetadata,
		})
	}

	return joinedList, nil
}
