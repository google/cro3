// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"fmt"
	"log"

	conf "go.chromium.org/chromiumos/config/go"
)

type OverwriteInstalCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewOverwriteInstalCommand(ctx context.Context, cs *service.CrOSService) *OverwriteInstalCommand {
	return &OverwriteInstalCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *OverwriteInstalCommand) Execute() error {
	if c.cs.OverwritePayload == nil {
		log.Printf("skipping overwrite install, because none was specified.")
		return nil
	}

	if c.cs.OverwritePayload.HostType == conf.StoragePath_LOCAL || c.cs.OverwritePayload.HostType == conf.StoragePath_HOSTTYPE_UNSPECIFIED {
		return fmt.Errorf("only GS copying is implemented")
	}

	err := c.cs.Connection.PipeData(c.ctx, c.cs.OverwritePayload.GetPath(), "tar xf - -C /")
	if err != nil {
		return fmt.Errorf("failed to download and untar file, %s", err)
	}

	if err := c.cs.Connection.Restart(c.ctx); err != nil {
		return fmt.Errorf("failed to restart dut, %s", err)
	}

	return nil
}

func (c *OverwriteInstalCommand) Revert() error {
	return nil
}

func (c *OverwriteInstalCommand) GetErrorMessage() string {
	return "failed to overwrite install"
}
