// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"fmt"
)

type CorrectDLCPermissionsCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewCorrectDLCPermissionsCommand(ctx context.Context, cs *service.CrOSService) *CorrectDLCPermissionsCommand {
	return &CorrectDLCPermissionsCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *CorrectDLCPermissionsCommand) Execute() error {
	// CorrectDLCPermissions changes the permission and ownership of DLC cache to
	// the correct one. As part of the transition to using tmpfiles.d, dlcservice
	// paths must have correct permissions/owners set. Simply starting the
	// dlcservice daemon will not fix this due to security concerns.
	if _, err := c.cs.Connection.RunCmd(c.ctx, "chown", []string{"-R", "dlcservice:dlcservice", common_utils.DlcCacheDir}); err != nil {
		return fmt.Errorf("unable to set owner for DLC cache (%s), %s", common_utils.DlcCacheDir, err)
	}

	if _, err := c.cs.Connection.RunCmd(c.ctx, "chmod", []string{"-R", "0755", common_utils.DlcCacheDir}); err != nil {
		return fmt.Errorf("unable to set permissions for DLC cache (%s), %s", common_utils.DlcCacheDir, err)
	}

	return nil
}

func (c *CorrectDLCPermissionsCommand) Revert() error {
	return nil
}

func (c *CorrectDLCPermissionsCommand) GetErrorMessage() string {
	return "failed to correct DLC permissions"
}
