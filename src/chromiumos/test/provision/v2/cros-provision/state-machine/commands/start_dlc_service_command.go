// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type StartDLCServiceCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewStartDLCServiceCommand(ctx context.Context, cs *service.CrOSService) *StartDLCServiceCommand {
	return &StartDLCServiceCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *StartDLCServiceCommand) Execute(log *log.Logger) error {
	log.Printf("Start StartDLCServiceCommand Execute")

	if _, err := c.cs.Connection.RunCmd(c.ctx, "start", []string{"dlcservice"}); err != nil {
		log.Printf("StartDLCServiceCommand start FAILED NON FATAL")

		log.Printf("%s, %s", c.GetErrorMessage(), err)
	}
	log.Printf("StartDLCServiceCommand Success")

	return nil
}

func (c *StartDLCServiceCommand) Revert() error {
	return nil
}

func (c *StartDLCServiceCommand) GetErrorMessage() string {
	return "failed to start DLC service"
}

func (c *StartDLCServiceCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_PROVISIONING_FAILED
}