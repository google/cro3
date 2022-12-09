// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// writeManifest will create and write the Lacros component manifest out.
package commands

import (
	"chromiumos/test/provision/v2/lacros-provision/service"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type WriteManifestCommand struct {
	ctx context.Context
	cs  *service.LaCrOSService
}

func NewWriteManifestCommand(ctx context.Context, cs *service.LaCrOSService) *WriteManifestCommand {
	return &WriteManifestCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *WriteManifestCommand) Execute(log *log.Logger) error {
	imageHash, err := c.getSHA256Sum(c.ctx, c.cs.GetLocalImagePath())
	if err != nil {
		return fmt.Errorf("failed to get Lacros image hash, %w", err)
	}
	tableHash, err := c.getSHA256Sum(c.ctx, c.cs.GetTablePath())
	if err != nil {
		return fmt.Errorf("failed to get Lacros table hash, %w", err)
	}
	lacrosManifestJSON, err := json.MarshalIndent(struct {
		ManifestVersion int    `json:"manifest-version"`
		FsType          string `json:"fs-type"`
		Version         string `json:"version"`
		ImageSha256Hash string `json:"image-sha256-hash"`
		TableSha256Hash string `json:"table-sha256-hash"`
	}{
		ManifestVersion: 1,
		FsType:          "squashfs",
		Version:         c.cs.LaCrOSMetadata.Content.Version,
		ImageSha256Hash: imageHash,
		TableSha256Hash: tableHash,
	}, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to Marshal Lacros manifest json, %w", err)
	}
	return c.cs.WriteToFile(c.ctx, string(lacrosManifestJSON), c.cs.GetManifestPath())
}

func (c *WriteManifestCommand) Revert() error {
	return nil
}

func (c *WriteManifestCommand) GetErrorMessage() string {
	return "failed to write manifest"
}

// getSHA256Sum will get the SHA256 sum of a file on the device.
func (c *WriteManifestCommand) getSHA256Sum(ctx context.Context, path string) (string, error) {
	hash, err := c.cs.Connection.RunCmd(ctx, "sha256sum", []string{
		path,
		"|",
		"cut", "-d' '", "-f1",
	})
	if err != nil {
		return "", fmt.Errorf("failed to get hash of %s, %w", path, err)
	}
	return strings.TrimSpace(hash), nil
}

func (c *WriteManifestCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_UPDATE_FIRMWARE_FAILED
}
