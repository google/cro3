// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"fmt"
	"log"
	"path/filepath"

	"go.chromium.org/chromiumos/config/go/test/api"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/service"
)

type CopyDataCommand struct {
	ctx context.Context
	svc *service.AndroidService
}

func NewCopyDataCommand(ctx context.Context, svc *service.AndroidService) *CopyDataCommand {
	return &CopyDataCommand{
		ctx: ctx,
		svc: svc,
	}
}

func (c *CopyDataCommand) Execute(log *log.Logger) error {
	log.Printf("Start CopyDataCommand Execute")
	switch s := c.ctx.Value("stage"); s {
	case common.PackageFetch:
		if err := copyPackages(c); err != nil {
			log.Printf("CopyDataCommand Failure: %v", err)
			return err
		}
	case common.OSFetch:
		if err := copyOsImages(c); err != nil {
			log.Printf("CopyDataCommand Failure: %v", err)
			return err
		}
	default:
		err := fmt.Errorf("unknown installation stage: %s", s)
		log.Printf("CopyDataCommand Failure: %v", err)
		return err
	}
	log.Printf("CopyDataCommand Success")
	return nil
}

func (c *CopyDataCommand) Revert() error {
	return nil
}

func (c *CopyDataCommand) GetErrorMessage() string {
	return "failed to copy data"
}

func (c *CopyDataCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_GS_DOWNLOAD_FAILED
}

func copyPackages(c *CopyDataCommand) error {
	for _, pkg := range c.svc.ProvisionPackages {
		if apkFile := pkg.APKFile; apkFile != nil {
			dstPath := filepath.Join("/tmp", pkg.CIPDPackage.InstanceId, apkFile.Name)
			dut := c.svc.DUT
			if err := dut.AssociatedHost.CreateDirectories(c.ctx, []string{filepath.Dir(dstPath)}); err != nil {
				return err
			}
			if err := dut.AssociatedHost.CopyData(c.ctx, apkFile.GsPath, dstPath); err != nil {
				return err
			}
			apkFile.DutPath = dstPath
		}
	}
	return nil
}

func copyOsImages(c *CopyDataCommand) error {
	// TODO: (jtamasleloup) Implement this functionality.
	return nil
}
