// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Deploy rsyncs files to the desired locations for installation
package commands

import (
	"chromiumos/test/provision/v2/ash-provision/service"
	"context"
	"fmt"
	"path/filepath"
)

// binaries to be copied in installation
var copyPaths = [...]string{
	"ash_shell",
	"aura_demo",
	"chrome",
	"chrome-wrapper",
	"chrome.pak",
	"chrome_100_percent.pak",
	"chrome_200_percent.pak",
	"content_shell",
	"content_shell.pak",
	"extensions/",
	"lib/*.so",
	"libffmpegsumo.so",
	"libpdf.so",
	"libppGoogleNaClPluginChrome.so",
	"libosmesa.so",
	"libwidevinecdmadapter.so",
	"libwidevinecdm.so",
	"locales/",
	"nacl_helper_bootstrap",
	"nacl_irt_*.nexe",
	"nacl_helper",
	"resources/",
	"resources.pak",
	"xdg-settings",
	"*.png",
}

// test binaries to be copied in installation
var testPaths = [...]string{
	"*test",
	"*tests",
}

type DeployCommand struct {
	ctx context.Context
	cs  *service.AShService
}

func NewDeployCommand(ctx context.Context, cs *service.AShService) *DeployCommand {
	return &DeployCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *DeployCommand) Execute() error {
	for _, file := range copyPaths {

		if err := c.deployFile(c.ctx, file, c.cs.GetTargetDir()); err != nil {
			return fmt.Errorf("could not deploy copy file, %w", err)
		}
	}
	for _, file := range testPaths {
		if err := c.deployFile(c.ctx, file, c.cs.GetAutotestDir()); err != nil {
			return fmt.Errorf("could not deploy autotest file, %w", err)
		}
		if err := c.deployFile(c.ctx, file, c.cs.GetTastDir()); err != nil {
			return fmt.Errorf("could not deploy tast file, %w", err)
		}
	}
	return nil
}

func (c *DeployCommand) Revert() error {
	return nil
}

func (c *DeployCommand) GetErrorMessage() string {
	return "failed to deploy ASh files"
}

// deployFile rsyncs one specific file to the desired bin dir
func (c *DeployCommand) deployFile(ctx context.Context, file string, destination string) error {
	source := fmt.Sprintf("%s/%s", c.cs.GetStagingDirectory(), file)
	target := filepath.Dir(fmt.Sprintf("%s/%s", destination, file))

	if exists, err := c.cs.Connection.PathExists(ctx, source); err != nil {
		return fmt.Errorf("failed to determine file existance, %s", err)
	} else if !exists {
		return nil
	}

	if _, err := c.cs.Connection.RunCmd(ctx, "rsync", []string{"-av", source, target}); err != nil {
		return fmt.Errorf("failed run rsync, %s", err)
	}
	return nil
}
