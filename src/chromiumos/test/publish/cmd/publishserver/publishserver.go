// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements publish_service.proto (see proto for details)
package publishserver

import (
	"context"
	"log"

	"chromiumos/lro"
	"chromiumos/test/publish/cmd/publishserver/storage"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
)

// PublishService implementation of publish_service.proto
type PublishService struct {
	manager  *lro.Manager
	logger   *log.Logger
	gsClient storage.GSClientInterface
}

// NewPublishService creates a new publish service with the GCP storage client.
func NewPublishService(ctx context.Context, gcpCredentials string, logger *log.Logger) (*PublishService, func(), error) {
	gsClient, err := storage.NewGSClient(ctx, gcpCredentials)
	if err != nil {
		return nil, nil, err
	}
	publishService := &PublishService{
		manager:  lro.New(),
		logger:   logger,
		gsClient: gsClient,
	}

	destructor := func() {
		publishService.manager.Close()
		publishService.gsClient.Close()
	}

	return publishService, destructor, nil
}

// UploadToGS uploads the designated folder to the provided Google Cloud Storage
// bucket/object
func (s *PublishService) UploadToGS(ctx context.Context, req *api.UploadToGSRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.UploadToGSRequest: ", req)
	op := s.manager.NewOperation()
	if err := s.gsClient.Upload(ctx, req.LocalDirectory, req.GsDirectory); err != nil {
		return nil, err
	}
	s.manager.SetResult(op.Name, &api.UploadToGSResponse{
		GsUrl: req.GsDirectory,
	})
	return op, nil
}
