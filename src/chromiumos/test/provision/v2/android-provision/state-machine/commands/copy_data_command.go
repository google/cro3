// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"

	"go.chromium.org/chromiumos/config/go/test/api"
	"golang.org/x/sync/errgroup"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/common/gsstorage"
	"chromiumos/test/provision/v2/android-provision/service"
)

type CopyDataCommand struct {
	ctx context.Context
	svc *service.AndroidService
	gs  gsstorage.GsClient
}

func NewCopyDataCommand(ctx context.Context, svc *service.AndroidService) *CopyDataCommand {
	return &CopyDataCommand{
		ctx: ctx,
		svc: svc,
		gs:  gsstorage.NewGsClient(common.GSImageBucketName),
	}
}

func (c *CopyDataCommand) Execute(log *log.Logger) error {
	log.Printf("Start CopyDataCommand Execute")
	switch s := c.ctx.Value("stage"); s {
	case common.PackageFetch:
		if err := c.copyPackages(); err != nil {
			log.Printf("CopyDataCommand Failure: %v", err)
			return err
		}
	case common.OSFetch:
		if err := c.copyOSImages(); err != nil {
			log.Printf("CopyDataCommand Failure: %v", err)
			return err
		}
	default:
		err := fmt.Errorf("unknown installation stage: %s", s)
		log.Printf("CopyDataCommand Failure: %v", err)
		return err
	}
	log.Printf("CopyDataCommand Success")
	return nil
}

func (c *CopyDataCommand) Revert() error {
	return nil
}

func (c *CopyDataCommand) GetErrorMessage() string {
	return "failed to copy data"
}

func (c *CopyDataCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_GS_DOWNLOAD_FAILED
}

// copyPackages uses caching-service to copy apks to associated host.
func (c *CopyDataCommand) copyPackages() error {
	for _, pkg := range c.svc.ProvisionPackages {
		if apkFile := pkg.APKFile; apkFile != nil {
			dstPath := filepath.Join("/tmp", pkg.CIPDPackage.InstanceId, apkFile.Name)
			dut := c.svc.DUT
			if err := dut.AssociatedHost.CopyData(c.ctx, apkFile.GsPath, dstPath); err != nil {
				return err
			}
			apkFile.DutPath = dstPath
		}
	}
	return nil
}

// copyOSImages uses caching-service to copy Android OS images to associated host stateful_partition.
// stateful_partition is used because the default /tmp folder lack memory space.
func (c *CopyDataCommand) copyOSImages() error {
	if c.svc.OS == nil || c.svc.OS.ImagePath.GsPath == "" {
		// Android OS provision is not requested or not needed.
		return nil
	}
	ctx := c.ctx
	imagePath := c.svc.OS.ImagePath
	folderPath := strings.Join(strings.Split(imagePath.GsPath, string(os.PathSeparator))[3:], string(os.PathSeparator))
	dstPath := filepath.Join("/mnt/stateful_partition/android_provision", folderPath)
	// List files' name from gcp.
	files, err := c.gs.ListFiles(ctx, folderPath, "/")
	if err != nil {
		return err
	}
	provisionFiles := getProvisionFiles(files)
	// Use caching service to copy files to temp directory.
	if err := c.cacheOSFiles(dstPath, provisionFiles); err != nil {
		return err
	}
	// Populate the list of images to flash and their location.
	imagePath.DutAndroidProductOut = dstPath
	imagePath.Files = provisionFiles
	return nil
}

// cacheOSFiles runs copyData for every files in parallel.
func (c *CopyDataCommand) cacheOSFiles(dstPath string, provisionFiles []string) error {
	if len(provisionFiles) != 3 {
		return fmt.Errorf("missing provision files")
	}
	svc := c.svc
	gsPath := svc.OS.ImagePath.GsPath
	dut := svc.DUT
	errs, ctx := errgroup.WithContext(c.ctx)
	for _, f := range provisionFiles {
		f := f
		errs.Go(func() error {
			gsFullPath := gsPath + f
			return dut.AssociatedHost.CopyData(ctx, gsFullPath, filepath.Join(dstPath, f))
		})
	}
	return errs.Wait()
}

// getProvisionFiles acts as a filter and returns only the files needed.
func getProvisionFiles(files []string) []string {
	var provisionFiles []string
	for _, f := range files {
		if len(provisionFiles) == 3 {
			break
		}
		if f == "radio.img" || f == "bootloader.img" || strings.HasSuffix(f, ".zip") {
			provisionFiles = append(provisionFiles, f)
		}
	}
	return provisionFiles
}
