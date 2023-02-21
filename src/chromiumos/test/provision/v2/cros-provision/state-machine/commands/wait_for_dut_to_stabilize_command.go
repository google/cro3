// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"errors"
	"log"
	"strings"
	"time"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type WaitForDutToStabilizeCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewWaitForDutToStabilizeCommand(ctx context.Context, cs *service.CrOSService) *WaitForDutToStabilizeCommand {
	return &WaitForDutToStabilizeCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *WaitForDutToStabilizeCommand) Execute(log *log.Logger) error {
	log.Printf("Start WaitForDutToStabilizeCommand Execute")
	fiveMinutes := time.Minute * 5
	twoSeconds := time.Second * 2

	// Note in CLI mode the context is not built with a timeout, thus we need to check on loop.
	for start := time.Now(); time.Since(start) < fiveMinutes; time.Sleep(twoSeconds) {
		select {
		case <-c.ctx.Done():
			return errors.New("failed to wait for UI to stablize, likely a bad image")
		default:
			status, err := c.cs.Connection.RunCmd(c.ctx, "status", []string{"system-services"})
			if err != nil {
				log.Printf("WaitForDutToStabilizeCommand could not get UI status, %s", err)
			} else if !strings.Contains(status, "start/running") {
				log.Printf("WaitForDutToStabilizeCommand UI has not stabilized yet")
			} else {
				log.Printf("WaitForDutToStabilizeCommand UI is running")
				log.Printf("WaitForDutToStabilizeCommand Success")
				return nil
			}
		}
	}
	return errors.New("failed to wait for UI to stablize, likely a bad image")
}

func (c *WaitForDutToStabilizeCommand) Revert() error {
	return nil
}

func (c *WaitForDutToStabilizeCommand) GetErrorMessage() string {
	return "failed to wait for DUT to stabilize"
}

func (c *WaitForDutToStabilizeCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_STABLIZE_DUT_FAILED
}
