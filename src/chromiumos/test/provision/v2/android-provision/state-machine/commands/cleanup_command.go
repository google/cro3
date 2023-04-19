// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"log"
	"os"
	"path/filepath"

	"go.chromium.org/chromiumos/config/go/test/api"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/service"
)

type CleanupCommand struct {
	ctx context.Context
	svc *service.AndroidService
}

func NewCleanupCommand(ctx context.Context, svc *service.AndroidService) *CleanupCommand {
	return &CleanupCommand{
		ctx: ctx,
		svc: svc,
	}
}

func (c *CleanupCommand) Execute(log *log.Logger) error {
	log.Printf("Start CleanupCommand Execute")
	if stage := c.ctx.Value("stage"); stage != nil {
		switch stage {
		case common.OSInstall:
			if osImage := c.svc.OS; osImage != nil && osImage.ImagePath.GsPath != "" {
				c.svc.DUT.AssociatedHost.DeleteDirectory(c.ctx, osImage.ImagePath.DutAndroidProductOut)
			}
		case common.PackageInstall:
			for _, pkg := range c.svc.ProvisionPackages {
				if apkFile := pkg.APKFile; apkFile != nil {
					c.svc.DUT.AssociatedHost.DeleteDirectory(c.ctx, filepath.Dir(apkFile.DutPath))
				}
			}
		case common.PostInstall:
			os.RemoveAll(c.svc.ProvisionDir)
		}
	}
	log.Printf("CleanupCommand Success")
	return nil
}

func (c *CleanupCommand) Revert() error {
	return nil
}

func (c *CleanupCommand) GetErrorMessage() string {
	return "failed to cleanup temp files"
}

func (c *CleanupCommand) GetStatus() api.InstallResponse_Status {
	if stage := c.ctx.Value("stage"); stage == common.PostInstall {
		return api.InstallResponse_STATUS_POST_PROVISION_SETUP_FAILED
	}
	return api.InstallResponse_STATUS_PROVISIONING_FAILED
}
