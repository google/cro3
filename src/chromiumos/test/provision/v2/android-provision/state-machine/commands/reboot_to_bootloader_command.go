// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"log"

	"chromiumos/test/provision/v2/android-provision/service"
	"go.chromium.org/chromiumos/config/go/test/api"
)

type RebootToBootloaderCommand struct {
	ctx context.Context
	svc *service.AndroidService
}

func NewRebootToBootloaderCommand(ctx context.Context, svc *service.AndroidService) *RebootToBootloaderCommand {
	return &RebootToBootloaderCommand{
		ctx: ctx,
		svc: svc,
	}
}

func (c *RebootToBootloaderCommand) Execute(log *log.Logger) error {
	log.Printf("Start RebootToBootloaderCommand Execute")
	if osImage := c.svc.OS; osImage != nil {
		if err := rebootToBootloader(c.ctx, c.svc.DUT, "adb"); err != nil {
			log.Printf("RebootToBootloaderCommand failed: %v", err)
			return err
		}
	}
	log.Printf("RebootToBootloaderCommand Success")
	return nil
}

func (c *RebootToBootloaderCommand) Revert() error {
	return nil
}

func (c *RebootToBootloaderCommand) GetErrorMessage() string {
	return "failed to reboot to bootloader"
}

func (c *RebootToBootloaderCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_PROVISIONING_FAILED
}
