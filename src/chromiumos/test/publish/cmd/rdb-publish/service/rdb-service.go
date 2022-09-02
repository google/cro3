// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package service

import (
	"context"

	common_utils "chromiumos/test/publish/cmd/common-utils"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/protobuf/proto"
)

type RdbPublishService struct {
	RetryCount int
}

func NewRdbPublishService(req *api.PublishRequest) (*RdbPublishService, error) {
	_, err := unpackMetadata(req)
	if err != nil {
		return nil, err
	}

	if err = common_utils.ValidateRDBPublishRequest(req, nil); err != nil {
		return nil, err
	}

	// TODO(b/241154998): read retryCount from input
	retryCount := 0

	return &RdbPublishService{
		RetryCount: retryCount,
	}, nil
}

// TODO(b/241154998): implement this
func (ts *RdbPublishService) UploadToRdb(ctx context.Context) error {
	return nil
}

// unpackMetadata unpacks the Any metadata field into PublishGcsMetadata
func unpackMetadata(req *api.PublishRequest) (*proto.Message, error) {
	var m proto.Message
	// TODO(b/241154998): unmarshal proper metadata
	return &m, nil
}
