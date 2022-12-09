// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/ash-provision/service"
	"context"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type StopChromeCommand struct {
	ctx context.Context
	cs  *service.AShService
}

func NewStopChromeCommand(ctx context.Context, cs *service.AShService) *StopChromeCommand {
	return &StopChromeCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *StopChromeCommand) Execute(log *log.Logger) error {
	if _, err := c.cs.Connection.RunCmd(c.ctx, "stop", []string{"ui"}); err != nil {
		// stop ui returns error when UI is terminated, so ignore error here
		log.Printf("failed to stop chrome, %s", err)
	}
	return nil
}

func (c *StopChromeCommand) Revert() error {
	return nil
}

func (c *StopChromeCommand) GetErrorMessage() string {
	return "failed to stop chrome"
}

func (c *StopChromeCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_PROVISIONING_FAILED
}
