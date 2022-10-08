// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"fmt"
	"log"
)

type WipeStatefulCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewWipeStatefulCommand(ctx context.Context, cs *service.CrOSService) *WipeStatefulCommand {
	return &WipeStatefulCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *WipeStatefulCommand) Execute(log *log.Logger) error {
	log.Printf("Start WipeStatefulCommand Execute")

	if !c.cs.PreserverStateful {
		if _, err := c.cs.Connection.RunCmd(c.ctx, "echo", []string{"'fast keepimg'", ">", "/mnt/stateful_partition/factory_install_reset"}); err != nil {
			return fmt.Errorf("failed to to write to factory reset file, %s", err)
		}

		if err := c.cs.Connection.Restart(c.ctx); err != nil {
			return fmt.Errorf("failed to restart dut, %s", err)
		}
	}
	log.Printf("WipeStatefulCommand Success")

	return nil
}

func (c *WipeStatefulCommand) Revert() error {
	return nil
}

func (c *WipeStatefulCommand) GetErrorMessage() string {
	return "failed to wipe stateful"
}
