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

	conf "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
)

type InstallDLCsCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewInstallDLCsCommand(ctx context.Context, cs *service.CrOSService) *InstallDLCsCommand {
	return &InstallDLCsCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *InstallDLCsCommand) Execute(log *log.Logger) error {
	log.Printf("Start InstallDLCsCommand Execute")
	activeSlot := common_utils.ActiveDlcMap[c.cs.MachineMetadata.RootInfo.RootPartNum]
	var err error
	errCh := make(chan error)
	for _, spec := range c.cs.DlcSpecs {
		go func(spec *api.CrOSProvisionMetadata_DLCSpec) {
			errCh <- c.installDLC(c.ctx, spec, activeSlot)
		}(spec)
	}
	log.Printf("InstallDLCsCommand installDLC completed")

	for range c.cs.DlcSpecs {
		errTmp := <-errCh
		if errTmp == nil {
			continue
		}
		err = fmt.Errorf("%s, %s", err, errTmp)
	}
	log.Printf("InstallDLCsCommand Success")
	return err
}

func (c *InstallDLCsCommand) Revert() error {
	return nil
}

// installDLC installs all relevant DLCs
func (c *InstallDLCsCommand) installDLC(ctx context.Context, spec *api.CrOSProvisionMetadata_DLCSpec, slot string) error {
	dlcID := spec.GetId()
	dlcOutputDir := path.Join(common_utils.DlcCacheDir, dlcID, common_utils.DlcPackage)
	verified, err := c.isDLCVerified(ctx, spec.GetId(), slot)
	if err != nil {
		return fmt.Errorf("failed is DLC verified check, %s", err)
	}

	// Skip installing the DLC if already verified.
	if verified {
		log.Printf("provision DLC %s skipped as already verified", dlcID)
		return nil
	}

	if c.cs.ImagePath.HostType == conf.StoragePath_LOCAL || c.cs.ImagePath.HostType == conf.StoragePath_HOSTTYPE_UNSPECIFIED {
		return fmt.Errorf("only GS copying is implemented")
	}
	dlcURL := path.Join(c.cs.ImagePath.GetPath(), "dlc", dlcID, common_utils.DlcPackage, common_utils.DlcImage)

	dlcOutputSlotDir := path.Join(dlcOutputDir, string(slot))
	dlcOutputImage := path.Join(dlcOutputSlotDir, common_utils.DlcImage)
	if err := c.cs.Connection.CreateDirectories(ctx, []string{dlcOutputSlotDir}); err != nil {
		return fmt.Errorf("failed to create DLC directories %s, %s", dlcID, err)
	}
	if err := c.cs.Connection.CopyData(ctx, dlcURL, dlcOutputImage); err != nil {
		return fmt.Errorf("failed to download DLCs, %s", err)
	}

	return nil
}

// isDLCVerified checks if the desired DLC already exists within the system
func (c *InstallDLCsCommand) isDLCVerified(ctx context.Context, dlcID, slot string) (bool, error) {
	verified, err := c.cs.Connection.PathExists(ctx, path.Join(common_utils.DlcLibDir, dlcID, slot, common_utils.DlcVerified))
	if err != nil {
		return false, fmt.Errorf("failed to check if DLC %s is verified, %s", dlcID, err)
	}
	return verified, nil
}

func (c *InstallDLCsCommand) GetErrorMessage() string {
	return "failed to install DLCs"
}
