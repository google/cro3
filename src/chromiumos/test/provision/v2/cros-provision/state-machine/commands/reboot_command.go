// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"log"
	"time"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type RebootCommand struct {
	timeout *time.Duration
	ctx     context.Context
	cs      *service.CrOSService
}

func NewRebootWithTimeoutCommand(timeout time.Duration, ctx context.Context, cs *service.CrOSService) *RebootCommand {
	return &RebootCommand{
		timeout: &timeout,
		ctx:     ctx,
		cs:      cs,
	}
}

func NewRebootCommand(ctx context.Context, cs *service.CrOSService) *RebootCommand {
	return &RebootCommand{
		timeout: nil,
		ctx:     ctx,
		cs:      cs,
	}
}

func (c *RebootCommand) Execute(log *log.Logger) error {
	log.Printf("Start RebootCommand Execute")

	ctx := c.ctx
	var cancel context.CancelFunc
	if c.timeout != nil {
		ctx, cancel = context.WithTimeout(context.Background(), *c.timeout)
		defer cancel()
	}
	if err := c.cs.Connection.Restart(ctx); err != nil {
		return err
	}
	log.Printf("RebootCommand Success")
	return nil
}

func (c *RebootCommand) Revert() error {
	return nil
}

func (c *RebootCommand) GetErrorMessage() string {
	return "failed to reboot DUT"
}

func (c *RebootCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_DUT_UNREACHABLE_POST_PROVISION
}
