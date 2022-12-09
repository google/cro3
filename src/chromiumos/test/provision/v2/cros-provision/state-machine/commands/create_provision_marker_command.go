// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type CreateProvisionMarkerCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewCreateProvisionMarkerCommand(ctx context.Context, cs *service.CrOSService) *CreateProvisionMarkerCommand {
	return &CreateProvisionMarkerCommand{
		ctx: ctx,
		cs:  cs,
	}

}

func (c *CreateProvisionMarkerCommand) Execute(log *log.Logger) error {
	log.Printf("Start CreateProvisionMarkerCommand Execute")
	if _, err := c.cs.Connection.RunCmd(c.ctx, "touch", []string{common_utils.ProvisionMarker}); err != nil {
		log.Printf("CreateProvisionMarkerCommand touch marker errord")
		return err
	}
	log.Printf("CreateProvisionMarkerCommand Success")
	return nil
}

func (c *CreateProvisionMarkerCommand) Revert() error {
	return nil
}

func (c *CreateProvisionMarkerCommand) GetErrorMessage() string {
	return "failed to create provision marker"
}

func (c *CreateProvisionMarkerCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_DUT_UNREACHABLE_PRE_PROVISION
}
