// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// GetMetadata translates the metadata from a file to a local JSON repr
package commands

import (
	lacros_metadata "chromiumos/test/provision/v2/lacros-provision/lacros-metadata"
	"chromiumos/test/provision/v2/lacros-provision/service"
	"context"
	"encoding/json"
)

type GetMetadataCommand struct {
	ctx context.Context
	cs  service.LaCrOSService
}

func NewGetMetadataCommand(ctx context.Context, cs service.LaCrOSService) *GetMetadataCommand {
	return &GetMetadataCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *GetMetadataCommand) Execute() error {
	metadataJSONStr, err := c.cs.Connection.RunCmd(c.ctx, "cat", []string{"/tmp/metadata.json"})
	if err != nil {
		return err
	}
	metadataJSON := lacros_metadata.LaCrOSMetadata{}
	if err := json.Unmarshal([]byte(metadataJSONStr), &metadataJSON); err != nil {
		return err
	}
	if c.cs.OverrideVersion != "" {
		metadataJSON.Content.Version = c.cs.OverrideVersion
	}
	c.cs.LaCrOSMetadata = &metadataJSON

	return nil
}

func (c *GetMetadataCommand) Revert() error {
	return nil
}

func (c *GetMetadataCommand) GetErrorMessage() string {
	return "failed to get metadata"
}
