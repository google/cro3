// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package coveragerules

import (
	"strings"

	"go.chromium.org/chromiumos/config/go/payload"
)

// flatConfigWrapper provides methods helpful when reading a FlatConfigList.
type flatConfigWrapper struct {
	flatConfigList   *payload.FlatConfigList
	programToConfigs map[string][]*payload.FlatConfig
}

func newFlatConfigWrapper(flatConfigList *payload.FlatConfigList) *flatConfigWrapper {
	return &flatConfigWrapper{flatConfigList: flatConfigList}
}

// getProgramConfigs returns all FlatConfigs for program.
//
// Similar to maps getProgramConfigs returns two values, the first is a list
// of FlatConfigs, if they are found for the program, the second is a bool
// indicating if the program exists in the FlatConfigList.
//
// Matching on program name is case-insensitive.
//
// The first call builds a map from program to FlatConfig, later calls reuse
// the map.
func (w *flatConfigWrapper) getProgramConfigs(program string) ([]*payload.FlatConfig, bool) {
	if w.programToConfigs == nil {
		w.programToConfigs = make(map[string][]*payload.FlatConfig)
		for _, flatConfig := range w.flatConfigList.Values {
			programID := strings.ToLower(flatConfig.GetProgram().GetId().GetValue())
			w.programToConfigs[programID] = append(w.programToConfigs[programID], flatConfig)
		}
	}

	flatConfig, ok := w.programToConfigs[strings.ToLower(program)]

	return flatConfig, ok
}
