// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"log"
	"path/filepath"

	"go.chromium.org/chromiumos/config/go/test/api"

	"chromiumos/test/provision/v2/android-provision/service"
)

type CopyAPKCommand struct {
	ctx context.Context
	svc *service.AndroidService
}

func NewCopyAPKCommand(ctx context.Context, svc *service.AndroidService) *CopyAPKCommand {
	return &CopyAPKCommand{
		ctx: ctx,
		svc: svc,
	}
}

func (c *CopyAPKCommand) Execute(log *log.Logger) error {
	log.Printf("Start CopyAPKCommand Execute")
	for _, pkg := range c.svc.ProvisionPackages {
		if apkFile := pkg.APKFile; apkFile != nil {
			dstPath := filepath.Join("/tmp", pkg.CIPDPackage.InstanceId, apkFile.Name)
			dut := c.svc.DUT
			if err := dut.AssociatedHost.CreateDirectories(c.ctx, []string{filepath.Dir(dstPath)}); err != nil {
				log.Printf("CopyAPKCommand Failure: %v", err)
				return err
			}
			if err := dut.AssociatedHost.CopyData(c.ctx, apkFile.GsPath, dstPath); err != nil {
				log.Printf("CopyAPKCommand Failure: %v", err)
				return err
			}
			apkFile.DutPath = dstPath
		}
	}
	log.Printf("CopyAPKCommand Success")
	return nil
}

func (c *CopyAPKCommand) Revert() error {
	return nil
}

func (c *CopyAPKCommand) GetErrorMessage() string {
	return "failed to copy APK file"
}

func (c *CopyAPKCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_GS_DOWNLOAD_FAILED
}
