// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package service

import (
	"context"
	"fmt"
	"log"

	common_utils "chromiumos/test/publish/cmd/common-utils"

	"go.chromium.org/chromiumos/config/go/test/api"
)

// TkoPublishService serves only one publish request. Not to be confused with a
// server that creates a new service instance for each request.
type TkoPublishService struct {
	LocalArtifactPath string
	RetryCount        int
	JobName           string
}

func NewTkoPublishService(req *api.PublishRequest) (*TkoPublishService, error) {
	metadata, err := unpackMetadata(req)
	if err != nil {
		return nil, err
	}

	if err = common_utils.ValidateTKOPublishRequest(req, metadata); err != nil {
		return nil, err
	}

	retryCount := 0
	if req.GetRetryCount() > 0 {
		retryCount = int(req.GetRetryCount())
	}

	return &TkoPublishService{
		LocalArtifactPath: req.GetArtifactDirPath().GetPath(),
		RetryCount:        retryCount,
		JobName:           metadata.GetJobName(),
	}, nil
}

func (ts *TkoPublishService) UploadToTko(ctx context.Context) error {
	cmd, err := tkoParseCmd(ctx, TkoParseRequest{ResultsDir: ts.LocalArtifactPath, JobName: ts.JobName})
	if err != nil {
		log.Printf("error while creating tko parse command: %s", err)
		return fmt.Errorf("error while creating tko parse command: %s", err)
	}
	_, _, err = common_utils.RunCommand(ctx, cmd, "tko/parse", nil, true)
	if err != nil {
		log.Printf("error in tko upload: %s", err)
		return fmt.Errorf("error in tko upload: %s", err)
	}
	return nil
}

// unpackMetadata unpacks the Any metadata field into PublishTkoMetadata
func unpackMetadata(req *api.PublishRequest) (*api.PublishTkoMetadata, error) {
	var m api.PublishTkoMetadata
	if err := req.Metadata.UnmarshalTo(&m); err != nil {
		return &m, fmt.Errorf("improperly formatted input proto metadata, %s", err)
	}
	return &m, nil
}
