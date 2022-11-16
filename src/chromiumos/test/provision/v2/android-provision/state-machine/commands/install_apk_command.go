// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"log"

	"chromiumos/test/provision/v2/android-provision/service"
)

type InstallAPKCommand struct {
	ctx context.Context
	svc *service.AndroidService
}

func NewInstallAPKCommand(ctx context.Context, svc *service.AndroidService) *InstallAPKCommand {
	return &InstallAPKCommand{
		ctx: ctx,
		svc: svc,
	}
}

func (c *InstallAPKCommand) Execute(log *log.Logger) error {
	log.Printf("Start InstallAPKCommand Execute")
	for _, pkg := range c.svc.ProvisionPackages {
		androidPkg := pkg.AndroidPackage
		if apkFile := pkg.APKFile; apkFile.ProvisionPath != "" {
			dut := c.svc.DUT
			args := []string{"-s", dut.SerialNumber, "install", "-r", "-d", "-g", apkFile.ProvisionPath}
			if _, err := dut.AssociatedHost.RunCmd(c.ctx, "adb", args); err != nil {
				log.Printf("InstallAPKCommand start failed: %v", err)
				return err
			}
			versionCode, err := getAndroidPackageVersionCode(c.ctx, dut, androidPkg.PackageName)
			if err != nil {
				log.Printf("InstallAPKCommand Failure: %v", err)
				// Falling back to the CIPD package version code
				versionCode = pkg.CIPDPackage.VersionCode
			}
			androidPkg.UpdatedVersionCode = versionCode
		}
	}
	log.Printf("InstallAPKCommand Success")
	return nil
}

func (c *InstallAPKCommand) Revert() error {
	return nil
}

func (c *InstallAPKCommand) GetErrorMessage() string {
	return "failed to install APK"
}
