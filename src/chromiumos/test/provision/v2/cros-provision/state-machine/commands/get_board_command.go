// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"fmt"
	"regexp"
)

var reBoard = regexp.MustCompile(`CHROMEOS_RELEASE_BOARD=(.*)`)

type GetBoardCommand struct {
	ctx context.Context
	cs  service.CrOSService
}

func NewGetBoardCommand(ctx context.Context, cs service.CrOSService) *GetBoardCommand {
	return &GetBoardCommand{
		ctx: ctx,
		cs:  cs,
	}

}

func (c *GetBoardCommand) Execute() error {
	board, err := c.getBoard()
	if err != nil {
		return fmt.Errorf("failed to get board, %s", err)
	}

	c.cs.MachineMetadata.Board = board

	return nil
}

func (c *GetBoardCommand) Revert() error {
	// Thought this method has side effects to the service it does not to the OS,
	// as such Revert here is unneded
	return nil
}

// getBoard returns the name of the current board
func (c *GetBoardCommand) getBoard() (string, error) {
	lsbRelease, err := c.cs.Connection.RunCmd(c.ctx, "cat", []string{"/etc/lsb-release"})
	if err != nil {
		return "", fmt.Errorf("failed to read lsb-release")
	}

	match := reBoard.FindStringSubmatch(lsbRelease)
	if match == nil {
		return "", fmt.Errorf("no match found in lsb-release for %s", reBoard.String())
	}
	return match[1], nil
}

func (c *GetBoardCommand) GetErrorMessage() string {
	return "failed to get board"
}
