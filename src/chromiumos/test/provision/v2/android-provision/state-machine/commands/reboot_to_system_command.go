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

type RebootToSystemCommand struct {
	ctx context.Context
	svc *service.AndroidService
}

func NewRebootToSystemCommand(ctx context.Context, svc *service.AndroidService) *RebootToSystemCommand {
	return &RebootToSystemCommand{
		ctx: ctx,
		svc: svc,
	}
}

func (c *RebootToSystemCommand) Execute(log *log.Logger) error {
	log.Printf("Start RebootToSystemCommand Execute")
	if osImage := c.svc.OS; osImage != nil {
		if err := rebootToSystem(c.ctx, c.svc.DUT, "fastboot"); err != nil {
			log.Printf("RebootToSystemCommand failed: %v", err)
			return err
		}
	}
	log.Printf("RebootToSystemCommand Success")
	return nil
}

func (c *RebootToSystemCommand) Revert() error {
	return nil
}

func (c *RebootToSystemCommand) GetErrorMessage() string {
	return "failed to reboot to system"
}

func (c *RebootToSystemCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_PROVISIONING_FAILED
}
