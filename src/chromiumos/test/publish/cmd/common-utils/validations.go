// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Validations functions
package common_utils

import (
	"fmt"
	"strings"

	_go "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/protobuf/proto"
)

// ValidateGCSPublishRequest validates gcs publish request
func ValidateGCSPublishRequest(req *api.PublishRequest, metadata *api.PublishGcsMetadata) error {
	if err := ValidateGenericPublishRequest(req); err != nil {
		return fmt.Errorf("error in publish request: %s", err)
	} else if err := ValidateGCSRequestMetadata(metadata); err != nil {
		return fmt.Errorf("error in gcs publish request metadata: %s", err)
	}
	return nil
}

// ValidateTKOPublishRequest validates tko publish request
func ValidateTKOPublishRequest(req *api.PublishRequest, metadata *api.PublishTkoMetadata) error {
	if err := ValidateGenericPublishRequest(req); err != nil {
		return fmt.Errorf("error in publish request: %s", err)
	} else if err := ValidateTKORequestMetadata(metadata); err != nil {
		return fmt.Errorf("error in tko publish request metadata: %s", err)
	}
	return nil
}

// ValidateTKOPublishRequest validates rdb publish request
func ValidateRDBPublishRequest(req *api.PublishRequest, metadata proto.Message) error {
	if err := ValidateGenericPublishRequest(req); err != nil {
		return fmt.Errorf("error in publish request: %s", err)
	}
	return nil
}

// ValidateGenericPublishRequest validates generic publish request
func ValidateGenericPublishRequest(req *api.PublishRequest) error {
	if req.GetArtifactDirPath().GetPath() == "" {
		return fmt.Errorf("local artifact dir path is empty")
	} else if req.GetArtifactDirPath().GetHostType() != _go.StoragePath_LOCAL {
		return fmt.Errorf("artifact dir path must be of type local")
	}
	return nil
}

// ValidateGCSRequestMetadata validates gcs request metadata
func ValidateGCSRequestMetadata(metadata *api.PublishGcsMetadata) error {
	if metadata.GetGcsPath().GetPath() == "" {
		return fmt.Errorf("GCS path is required in metadata for gcs publish")
	} else if metadata.GetGcsPath().GetHostType() != _go.StoragePath_GS {
		return fmt.Errorf("GCS path must be of GS type")
	} else if !strings.HasPrefix(metadata.GetGcsPath().GetPath(), "gs://") {
		return fmt.Errorf("gs url must begin with 'gs://', instead have, %s", metadata.GetGcsPath().GetPath())
	}

	return nil
}

// ValidateTKORequestMetadata validates tko request metadata
func ValidateTKORequestMetadata(metadata *api.PublishTkoMetadata) error {
	if metadata.GetJobName() == "" {
		return fmt.Errorf("JobName is required in metadata for tko publish")
	}

	return nil
}
