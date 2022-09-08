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
	"path"
	"strings"
)

type PostInstallCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewPostInstallCommand(ctx context.Context, cs *service.CrOSService) *PostInstallCommand {
	return &PostInstallCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *PostInstallCommand) Execute() error {
	tmpMnt, err := c.cs.Connection.RunCmd(c.ctx, "mktemp", []string{"-d"})
	if err != nil {
		return fmt.Errorf("failed to create temporary directory, %s", err)
	}
	tmpMnt = strings.TrimSpace(tmpMnt)
	if _, err := c.cs.Connection.RunCmd(c.ctx, "mount", []string{"-o", "ro", c.cs.MachineMetadata.RootInfo.PartitionInfo.InactiveRoot, tmpMnt}); err != nil {
		return fmt.Errorf("failed to mount inactive root, %s", err)
	}
	if _, err := c.cs.Connection.RunCmd(c.ctx, fmt.Sprintf("%s/postinst", tmpMnt), []string{c.cs.MachineMetadata.RootInfo.PartitionInfo.InactiveRoot}); err != nil {
		return fmt.Errorf("failed to postinst from inactive root, %s", err)
	}
	if _, err := c.cs.Connection.RunCmd(c.ctx, "umount", []string{tmpMnt}); err != nil {
		return fmt.Errorf("failed to umount temporary directory, %s", err)
	}
	if _, err := c.cs.Connection.RunCmd(c.ctx, "rmdir", []string{tmpMnt}); err != nil {
		return fmt.Errorf("failed to remove temporary directory, %s", err)
	}
	return nil
}

func (c *PostInstallCommand) Revert() error {
	c.revertStatefulInstall()
	c.revertPostInstall()
	return nil
}

// RevertStatefulInstall literally reverses a stateful installation
func (c *PostInstallCommand) revertStatefulInstall() {
	varNewPath := path.Join(common_utils.StatefulPath, "var_new")
	devImageNewPath := path.Join(common_utils.StatefulPath, "dev_image_new")
	_, err := c.cs.Connection.RunCmd(c.ctx, "rm", []string{"-rf", varNewPath, devImageNewPath, common_utils.UpdateStatefulFilePath})
	if err != nil {
		log.Printf("revert stateful install: failed to revert stateful installation, %s", err)
	}
}

// RevertPostInstall literally reverses a PostInstall
func (c *PostInstallCommand) revertPostInstall() {
	if _, err := c.cs.Connection.RunCmd(c.ctx, "/postinst", []string{c.cs.MachineMetadata.RootInfo.PartitionInfo.ActiveRoot, "2>&1"}); err != nil {
		log.Printf("revert post install: failed to revert postinst, %s", err)
	}
}

func (c *PostInstallCommand) GetErrorMessage() string {
	return "failed to post install"
}
