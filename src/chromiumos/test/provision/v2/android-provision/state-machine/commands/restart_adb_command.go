// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"fmt"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/service"
)

type RestartADBCommand struct {
	ctx context.Context
	svc *service.AndroidService
}

func NewRestartADBCommand(ctx context.Context, svc *service.AndroidService) *RestartADBCommand {
	return &RestartADBCommand{
		ctx: ctx,
		svc: svc,
	}
}

func (c *RestartADBCommand) Execute(log *log.Logger) error {
	log.Printf("Start RestartADBCommand Execute")
	dut := c.svc.DUT
	if _, err := dut.AssociatedHost.RunCmd(c.ctx, "adb", []string{"kill-server"}); err != nil {
		log.Printf("RestartADBCommand failed: %v", err)
		return err
	}
	if err := dut.AssociatedHost.CreateDirectories(c.ctx, []string{common.ADBUnixSocketMountDirectory}); err != nil {
		log.Printf("RestartADBCommand failed: %v", err)
		return err
	}
	cmd := fmt.Sprintf("ADB_VENDOR_KEYS=%s adb", common.ADBVendorKeys)
	if _, err := dut.AssociatedHost.RunCmd(c.ctx, cmd, []string{"start-server"}); err != nil {
		log.Printf("RestartADBCommand failed: %v", err)
		return err
	}
	log.Printf("RestartADBCommand Success")
	return nil
}

func (c *RestartADBCommand) Revert() error {
	return nil
}

func (c *RestartADBCommand) GetErrorMessage() string {
	return "failed to restart ADB service"
}

func (c *RestartADBCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_DUT_UNREACHABLE_PRE_PROVISION
}
