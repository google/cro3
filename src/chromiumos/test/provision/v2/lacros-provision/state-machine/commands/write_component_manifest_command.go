// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// writeComponentManifest will create and write the Lacros component manifest out usable by component updater.
package commands

import (
	"chromiumos/test/provision/v2/lacros-provision/service"
	"context"
	"encoding/json"
	"fmt"
)

type WriteComponentManifestCommand struct {
	ctx context.Context
	cs  *service.LaCrOSService
}

func NewWriteComponentManifestCommand(ctx context.Context, cs *service.LaCrOSService) *WriteComponentManifestCommand {
	return &WriteComponentManifestCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *WriteComponentManifestCommand) Execute() error {
	lacrosComponentManifestJSON, err := json.MarshalIndent(struct {
		ManifestVersion int    `json:"manifest-version"`
		Name            string `json:"name"`
		Version         string `json:"version"`
		ImageName       string `json:"imageName"`
		Squash          bool   `json:"squash"`
		FsType          string `json:"fsType"`
		IsRemovable     bool   `json:"isRemovable"`
	}{
		ManifestVersion: 2,
		Name:            "lacros",
		Version:         c.cs.LaCrOSMetadata.Content.Version,
		ImageName:       "image.squash",
		Squash:          true,
		FsType:          "squashfs",
		IsRemovable:     false,
	}, "", "  ")
	if err != nil {
		return fmt.Errorf("writeComponentManifest: failed to Marshal Lacros manifest json, %w", err)
	}
	return c.cs.WriteToFile(c.ctx, string(lacrosComponentManifestJSON), c.cs.GetComponentManifestPath())
}

func (c *WriteComponentManifestCommand) Revert() error {
	return nil
}

func (c *WriteComponentManifestCommand) GetErrorMessage() string {
	return "failed to write component manifest"
}
