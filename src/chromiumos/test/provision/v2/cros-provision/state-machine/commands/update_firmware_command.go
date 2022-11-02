// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"fmt"
	"log"
)

type RunFirmwareUpdaterCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewRunFirmwareUpdaterCommand(ctx context.Context, cs *service.CrOSService) *RunFirmwareUpdaterCommand {
	return &RunFirmwareUpdaterCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *RunFirmwareUpdaterCommand) Execute(log *log.Logger) error {
	log.Printf("Start RunFirmwareUpdaterCommand Execute")

	if _, err := c.cs.Connection.RunCmd(c.ctx, common_utils.FirmwareUpdaterPath, []string{"--wp=1", "--mode=autoupdate"}); err != nil {
		return fmt.Errorf("run firmware updater: %s", err)
	}

	log.Printf("RunFirmwareUpdaterCommand Success")

	return nil
}

func (c *RunFirmwareUpdaterCommand) Revert() error {
	return nil
}

func (c *RunFirmwareUpdaterCommand) GetErrorMessage() string {
	return "failed to run firmware updater"
}
