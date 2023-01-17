// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"fmt"
	"log"
	"regexp"

	"go.chromium.org/chromiumos/config/go/test/api"
)

var reVersion = regexp.MustCompile(`CHROMEOS_RELEASE_BUILDER_PATH=(.*)`)

// GetVersionCommand is the commands interface struct.
type GetVersionCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

// NewGetVersionCommand is the commands interface to GetVersionCommand
func NewGetVersionCommand(ctx context.Context, cs *service.CrOSService) *GetVersionCommand {
	return &GetVersionCommand{
		ctx: ctx,
		cs:  cs,
	}

}

// Execute is the executor for the command. Will get the OS version from the DUT.
func (c *GetVersionCommand) Execute(log *log.Logger) error {
	log.Printf("RUNNING GetVersionCommand Execute")
	version, err := c.getVersion()
	if err != nil {
		return fmt.Errorf("failed to get board, %s", err)
	}

	c.cs.MachineMetadata.Version = version
	log.Printf("RUNNING GetVersionCommand Success")

	return nil
}

// Revert interface command. None needed as nothing has happened yet.
func (c *GetVersionCommand) Revert() error {
	// Thought this method has side effects to the service it does not to the OS,
	// as such Revert here is unneeded
	return nil
}

// getVersion returns the name of the current board
func (c *GetVersionCommand) getVersion() (string, error) {
	lsbRelease, err := c.cs.Connection.RunCmd(c.ctx, "cat", []string{"/etc/lsb-release"})
	if err != nil {
		return "", fmt.Errorf("failed to read lsb-release")
	}

	match := reVersion.FindStringSubmatch(lsbRelease)
	if match == nil {
		return "", fmt.Errorf("no match found in lsb-release for %s", reVersion.String())
	}
	return match[1], nil
}

// GetErrorMessage provides the failed to check install err string.
func (c *GetVersionCommand) GetErrorMessage() string {
	return "failed to get board"
}

// GetStatus provides API Error reason.
func (c *GetVersionCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_PRE_PROVISION_SETUP_FAILED
}
