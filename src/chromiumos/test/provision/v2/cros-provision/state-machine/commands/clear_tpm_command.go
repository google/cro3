// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"strings"
)

type ClearTPMCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewClearTPMCommand(ctx context.Context, cs *service.CrOSService) *ClearTPMCommand {
	return &ClearTPMCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *ClearTPMCommand) Execute() error {
	if c.canClearTPM(c.ctx) {
		if _, err := c.cs.Connection.RunCmd(c.ctx, "crossystem", []string{"clear_tpm_owner_request=1"}); err != nil {
			return err
		}
	}

	return nil
}

// CanClearTPM determines whether the current board can clear TPM
func (c *ClearTPMCommand) canClearTPM(ctx context.Context) bool {
	return !strings.HasPrefix(c.cs.MachineMetadata.Board, "raven")
}

func (c *ClearTPMCommand) Revert() error {
	return nil
}

func (c *ClearTPMCommand) GetErrorMessage() string {
	return "failed to clear TPM"
}
