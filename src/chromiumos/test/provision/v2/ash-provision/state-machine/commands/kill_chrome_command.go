// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/ash-provision/service"
	"context"
	"fmt"
	"log"
	"time"
)

// Time specific consts
const (
	twoSeconds = 2 * time.Second
	tenSeconds = 10 * time.Second
)

type KillChromeCommand struct {
	ctx context.Context
	cs  *service.AShService
}

func NewKillChromeCommand(ctx context.Context, cs *service.AShService) *KillChromeCommand {
	return &KillChromeCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *KillChromeCommand) Execute(log *log.Logger) error {
	for start := time.Now(); time.Since(start) < tenSeconds; time.Sleep(twoSeconds) {
		if !c.isChromeInUse() {
			return nil
		}
		log.Printf("chrome binary is still running, killing...")
		if _, err := c.cs.Connection.RunCmd(c.ctx, "pkill", []string{"'chrome|session_manager'"}); err != nil {
			return err
		}
	}
	return fmt.Errorf("pkill did not kill chrome in the designated time")
}

func (c *KillChromeCommand) Revert() error {
	return nil
}

func (c *KillChromeCommand) GetErrorMessage() string {
	return "failed to kill chrome"
}

// isChromeInUse determines if chrome is currently running
func (c *KillChromeCommand) isChromeInUse() bool {
	_, err := c.cs.Connection.RunCmd(c.ctx, "lsof", []string{fmt.Sprintf("%s/chrome", c.cs.GetTargetDir())})
	return err != nil
}
