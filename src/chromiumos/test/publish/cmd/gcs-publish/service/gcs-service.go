// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package service

import (
	"context"
	"fmt"
	"log"

	common_utils "chromiumos/test/publish/cmd/common-utils"
	"chromiumos/test/publish/cmd/publishserver/storage"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type GcsPublishService struct {
	LocalArtifactPath           string
	GcsPath                     string
	ServiceAccountCredsFilePath string
	RetryCount                  int
}

func NewGcsPublishService(req *api.PublishRequest) (*GcsPublishService, error) {
	m, err := unpackMetadata(req)
	if err != nil {
		return nil, err
	}

	if err = common_utils.ValidateGCSPublishRequest(req, m); err != nil {
		return nil, err
	}

	retryCount := 0
	if req.GetRetryCount() > 0 {
		retryCount = int(req.GetRetryCount())
	}

	return &GcsPublishService{
		LocalArtifactPath:           req.GetArtifactDirPath().GetPath(),
		GcsPath:                     m.GetGcsPath().GetPath(),
		RetryCount:                  retryCount,
		ServiceAccountCredsFilePath: m.GetServiceAccountCredsFilePath().GetPath(),
	}, nil
}

func (gs *GcsPublishService) UploadToGS(ctx context.Context) error {
	gsClient, err := storage.NewGSClient(ctx, gs.ServiceAccountCredsFilePath)
	if err != nil {
		log.Printf("error while creating new gs client: %s", err)
		return fmt.Errorf("error while creating new gs client: %s", err)
	}

	if err := gsClient.Upload(ctx, gs.LocalArtifactPath, gs.GcsPath); err != nil {
		log.Printf("error in gcs upload: %s", err)
		return fmt.Errorf("error in gcs upload: %s", err)
	}
	return nil
}

// unpackMetadata unpacks the Any metadata field into PublishGcsMetadata
func unpackMetadata(req *api.PublishRequest) (*api.PublishGcsMetadata, error) {
	var m api.PublishGcsMetadata
	if err := req.Metadata.UnmarshalTo(&m); err != nil {
		return &m, fmt.Errorf("improperly formatted input proto metadata, %s", err)
	}
	return &m, nil
}
