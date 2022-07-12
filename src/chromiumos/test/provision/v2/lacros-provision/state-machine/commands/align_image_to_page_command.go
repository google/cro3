// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// AlignImageToPage will align the file to LacrosPageSize page alignment and return the number of page blocks.
package commands

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/info"
	"chromiumos/test/provision/v2/lacros-provision/service"
	"context"
	"fmt"
	"log"
	"strconv"
	"strings"
)

type AlignImageToPageCommand struct {
	ctx context.Context
	cs  *service.LaCrOSService
}

func NewAlignImageToPageCommand(ctx context.Context, cs *service.LaCrOSService) *AlignImageToPageCommand {
	return &AlignImageToPageCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *AlignImageToPageCommand) Execute() error {
	sizeStr, err := c.cs.Connection.RunCmd(c.ctx, "stat", []string{"-c%s", c.cs.GetLocalImagePath()})
	if err != nil {
		return fmt.Errorf("failed to get image size, %w", err)
	}
	size, err := strconv.Atoi(strings.TrimSpace(sizeStr))
	if err != nil {
		return fmt.Errorf("failed to get image size as an integer, %w", err)
	}

	// Round up to the nearest LaCrOSPageSize block size.
	blocks := (size + info.LaCrOSPageSize - 1) / info.LaCrOSPageSize

	// Check if the Lacros image is LacrosPageSize  aligned, if not extend it to LacrosPageSize alignment.
	if size != blocks*info.LaCrOSPageSize {
		log.Printf("image %s isn't aligned to %d, so extending it", c.cs.GetLocalImagePath(), info.LaCrOSPageSize)
		inputBlockCount := blocks*info.LaCrOSPageSize - size
		if _, err := c.cs.Connection.RunCmd(
			c.ctx,
			"dd",
			[]string{"if=/dev/zero",
				"bs=1",
				fmt.Sprintf("count=%d", inputBlockCount),
				fmt.Sprintf("seek=%d", size),
				fmt.Sprintf("of=%s", c.cs.GetLocalImagePath()),
			}); err != nil {
			return err
		}
	}
	c.cs.Blocks = blocks
	return nil
}

func (c *AlignImageToPageCommand) Revert() error {
	return nil
}

func (c *AlignImageToPageCommand) GetErrorMessage() string {
	return "failed to align image"
}
