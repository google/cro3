// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common_utils

import (
	"fmt"
	"os"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/chromiumos/config/go/test/api"
)

// ParseCrosProvisionRequest parses CrosProvisionRequest input request data from
// the input file.
func ParseCrosProvisionRequest(path string) (*api.CrosProvisionRequest, error) {
	in := &api.CrosProvisionRequest{}
	r, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("read input: %s", err)
	}

	umrsh := jsonpb.Unmarshaler{}
	umrsh.AllowUnknownFields = true
	err = umrsh.Unmarshal(r, in)
	if err != nil {
		return nil, fmt.Errorf("read input: %s", err)
	}

	return in, nil
}

// ParseProvisionFirmwareRequest parses ProvisionFirmwareRequest input request data from
// the input file.
func ParseProvisionFirmwareRequest(path string) (*api.ProvisionFirmwareRequest, error) {
	in := &api.ProvisionFirmwareRequest{}
	r, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("read input: %s", err)
	}

	umrsh := jsonpb.Unmarshaler{}
	umrsh.AllowUnknownFields = false
	err = umrsh.Unmarshal(r, in)
	if err != nil {
		return nil, fmt.Errorf("read input: %s", err)
	}

	return in, nil
}
