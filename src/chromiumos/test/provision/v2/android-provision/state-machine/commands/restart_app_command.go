// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"log"

	"chromiumos/test/provision/v2/android-provision/common"
	"go.chromium.org/chromiumos/config/go/test/api"

	"chromiumos/test/provision/v2/android-provision/service"
)

type RestartAppCommand struct {
	ctx context.Context
	svc *service.AndroidService
}

func NewRestartAppCommand(ctx context.Context, svc *service.AndroidService) *RestartAppCommand {
	return &RestartAppCommand{
		ctx: ctx,
		svc: svc,
	}
}

func (c *RestartAppCommand) Execute(log *log.Logger) error {
	log.Printf("Start RestartAppCommand Execute")
	dut := c.svc.DUT
	for _, pkg := range c.svc.ProvisionPackages {
		if androidPkg := pkg.AndroidPackage; androidPkg != nil {
			switch p := androidPkg.PackageName; p {
			case common.GMSCorePackageName:
				intent := "com.google.android.gms.INITIALIZE"
				args := [2][]string{
					{"-s", dut.SerialNumber, "shell", "am", "force-stop", p},
					{"-s", dut.SerialNumber, "shell", "am", "broadcast", "-a", intent}}
				for _, arg := range args {
					if _, err := dut.AssociatedHost.RunCmd(c.ctx, "adb", arg); err != nil {
						log.Printf("RestartAppCommand failed: %v", err)
						return err
					}
				}
			}
		}
	}
	log.Printf("RestartAppCommand Success")
	return nil
}

func (c *RestartAppCommand) Revert() error {
	return nil
}

func (c *RestartAppCommand) GetErrorMessage() string {
	return "failed to restart application"
}

func (c *RestartAppCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_POST_PROVISION_SETUP_FAILED
}
