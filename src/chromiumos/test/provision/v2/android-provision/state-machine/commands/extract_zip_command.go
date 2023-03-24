// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"log"
	"path/filepath"
	"strings"

	"chromiumos/test/provision/v2/android-provision/common"
	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"

	"chromiumos/test/provision/v2/android-provision/common/zip"
	"chromiumos/test/provision/v2/android-provision/service"
)

type ExtractZipCommand struct {
	ctx context.Context
	svc *service.AndroidService
	zip zip.ZipReader
}

func NewExtractZipCommand(ctx context.Context, svc *service.AndroidService) *ExtractZipCommand {
	return &ExtractZipCommand{
		ctx: ctx,
		svc: svc,
		zip: &zip.Zip{},
	}
}

func (c *ExtractZipCommand) Execute(log *log.Logger) error {
	log.Printf("Start ExtractZipCommand Execute")
	var err error
	if stage := c.ctx.Value("stage"); stage != nil {
		switch stage {
		case common.PackageFetch:
			err = c.extractCIPDPackages()
		case common.OSFetch:
			err = c.extractOsImage()
		}
	} else {
		err = errors.Reason("provision stage is not set").Err()
	}
	if err != nil {
		log.Printf("ExtractZipCommand Failure: %v", err)
		return err
	}
	log.Printf("ExtractZipCommand Success")
	return nil
}

func (c *ExtractZipCommand) Revert() error {
	return nil
}

func (c *ExtractZipCommand) GetErrorMessage() string {
	return "failed to extract zip file"
}

func (c *ExtractZipCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_PRE_PROVISION_SETUP_FAILED
}

// extractOsImage extract OS images from a zip file uploaded to associated host.
func (c *ExtractZipCommand) extractOsImage() error {
	osImage := c.svc.OS
	if osImage == nil || !strings.HasSuffix(osImage.ImagePath.GsPath, ".zip") {
		// There is no zipped image. Nothing to extract
		return nil
	}
	dut := c.svc.DUT
	dutProvisionDir := c.svc.OS.ImagePath.DutAndroidProductOut
	zipFile := filepath.Join(dutProvisionDir, filepath.Base(osImage.ImagePath.GsPath))
	// List the image files to extract
	args := []string{"-1", zipFile, "|", "grep", "-E", "'\\.(img|zip)$'", "|", "awk", "'{print}'", "ORS=' '"}
	files, err := dut.AssociatedHost.RunCmd(c.ctx, "zipinfo", args)
	if err != nil {
		return err
	}
	if files == "" {
		return errors.Reason("image files not found").Err()
	}
	// Unzip the image files
	args = []string{"-oq", zipFile, files, "-d", dutProvisionDir}
	if _, err = dut.AssociatedHost.RunCmd(c.ctx, "unzip", args); err != nil {
		return err
	}
	// Populate the list of image files to flash
	c.svc.OS.ImagePath.Files = strings.Fields(files)
	return nil
}

// extractCIPDPackages extracts Android package (APK) file from CIPD package
// downloaded to provision server.
func (c *ExtractZipCommand) extractCIPDPackages() error {
	for _, pkg := range c.svc.ProvisionPackages {
		if cipdPkg := pkg.CIPDPackage; cipdPkg.FilePath != "" {
			dstPath := filepath.Join(c.svc.ProvisionDir, cipdPkg.InstanceId)
			if err := c.zip.UnzipFile(cipdPkg.FilePath, dstPath); err != nil {
				return err
			}
		}
	}
	return nil
}
