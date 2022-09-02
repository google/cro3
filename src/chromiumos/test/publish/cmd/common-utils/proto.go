// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common_utils

import (
	"fmt"
	"os"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/protobuf/encoding/protojson"
)

// ParsePublishRequest parses PublishRequest input request data from
// the input file.
func ParsePublishRequest(path string) (*api.PublishRequest, error) {
	in := &api.PublishRequest{}
	r, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("error while opening file at %s: %s", path, err)
	}

	data, err := os.ReadFile(r.Name())
	if err != nil {
		return nil, fmt.Errorf("error while reading file %s: %s", r.Name(), err)
	}

	umrsh := protojson.UnmarshalOptions{
		DiscardUnknown: true,
	}
	err = umrsh.Unmarshal(data, in)
	if err != nil {
		return nil, fmt.Errorf("err while unmarshalling: %s", err)
	}

	return in, nil
}
