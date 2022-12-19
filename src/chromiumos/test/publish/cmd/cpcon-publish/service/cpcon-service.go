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

// CpconPublishService serves only one publish request. Not to be confused with a
// server that creates a new service instance for each request.
type CpconPublishService struct {
	LocalArtifactPath string
	RetryCount        int
}

func NewCpconPublishService(req *api.PublishRequest) (*CpconPublishService, error) {
	retryCount := 0
	if req.GetRetryCount() > 0 {
		retryCount = int(req.GetRetryCount())
	}

	return &CpconPublishService{
		LocalArtifactPath: req.GetArtifactDirPath().GetPath(),
		RetryCount:        retryCount,
	}, nil
}

func (ts *CpconPublishService) UploadToCpcon(ctx context.Context) error {
	cmd, err := uploadResultsCmd(ctx, CpconUploadRequest{ResultsDir: ts.LocalArtifactPath})
	if err != nil {
		log.Printf("error while creating upload results command: %s", err)
		return fmt.Errorf("error while creating upload results command: %s", err)
	}
	stdout, stderr, err := common_utils.RunCommand(ctx, cmd, "cpcon_upload_results", nil, true)
	if err != nil {
		log.Printf("cpcon upload cmd stdout: %s, cpcon upload cmd stderr: %s", stdout, stderr)
		return fmt.Errorf("error in cpcon upload results: %s", err)
	}
	return nil
}
