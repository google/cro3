// Copyright 2023 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"log"

	"chromiumos/test/provision/v2/android-provision/common/gsstorage"
	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"

	"chromiumos/test/provision/v2/android-provision/service"
)

type ResolveImagePathCommand struct {
	ctx context.Context
	svc *service.AndroidService
}

func NewResolveImagePathCommand(ctx context.Context, svc *service.AndroidService) *ResolveImagePathCommand {
	return &ResolveImagePathCommand{
		ctx: ctx,
		svc: svc,
	}
}

func (c *ResolveImagePathCommand) Execute(log *log.Logger) error {
	log.Printf("Start ResolveImagePathCommand Execute")
	if c.svc.OS != nil {
		if boardToBuildId := c.svc.OS.ImagePath.BoardToBuildID; boardToBuildId != nil {
			board := c.svc.DUT.Board
			buildId, ok := boardToBuildId[board]
			if !ok {
				err := errors.Reason("Android image not found for %s board", board).Err()
				log.Printf("ResolveImagePathCommand Failure: %v", err)
				return err
			}
			c.svc.OS.ImagePath.GsPath = gsstorage.GetGsPath("", buildId, board)
		}
	}
	log.Printf("ResolveImagePathCommand Success")
	return nil
}

func (c *ResolveImagePathCommand) Revert() error {
	return nil
}

func (c *ResolveImagePathCommand) GetErrorMessage() string {
	return "failed to resolve GS image path"
}

func (c *ResolveImagePathCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_PRE_PROVISION_SETUP_FAILED
}
