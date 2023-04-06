// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"log"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"chromiumos/test/provision/v2/android-provision/service"
	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"
)

type FlashOsCommand struct {
	ctx context.Context
	svc *service.AndroidService
}

func NewFlashOsCommand(ctx context.Context, svc *service.AndroidService) *FlashOsCommand {
	return &FlashOsCommand{
		ctx: ctx,
		svc: svc,
	}
}

func (c *FlashOsCommand) Execute(log *log.Logger) error {
	log.Printf("Start FlashOsCommand Execute")
	if osImage := c.svc.OS; osImage != nil {
		// Flashing bootloader and radio partitions.
		partitions := []string{"bootloader", "radio"}
		for _, p := range partitions {
			if err := c.flashPartition(p); err != nil {
				log.Printf("FlashOsCommand failed: %v", err)
				return err
			}
			if err := rebootToBootloader(c.ctx, c.svc.DUT, "fastboot"); err != nil {
				log.Printf("FlashOsCommand failed: %v", err)
				return err
			}
		}
		// Flashing all other partitions, keeping user data.
		if err := c.flashAll(); err != nil {
			log.Printf("FlashOsCommand failed: %v", err)
			return err
		}
		// Device takes some time to boot after flashing.
		maxWaitTime := 120 * time.Second
		if err := waitForDevice(c.ctx, c.svc.DUT, maxWaitTime); err != nil {
			log.Printf("FlashOsCommand failed: %v", err)
			return err
		}
		// Fetch the updated OS info
		if err := c.fetchOSInfo(); err != nil {
			log.Printf("FlashOsCommand failed: %v", err)
			return err
		}
	}
	log.Printf("FlashOsCommand Success")
	return nil
}

func (c *FlashOsCommand) Revert() error {
	return nil
}

func (c *FlashOsCommand) GetErrorMessage() string {
	return "failed to flash Android OS"
}

func (c *FlashOsCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_PROVISIONING_FAILED
}

func (c *FlashOsCommand) flashPartition(partition string) error {
	re, err := regexp.Compile(`^` + partition + `[-.].*img$`)
	if err != nil {
		return err
	}
	for _, f := range c.svc.OS.ImagePath.Files {
		if re.MatchString(filepath.Base(f)) {
			dut := c.svc.DUT
			provisionDir := c.svc.OS.ImagePath.DutAndroidProductOut
			args := []string{"-s", dut.SerialNumber, "flash", partition, filepath.Join(provisionDir, f)}
			_, err = dut.AssociatedHost.RunCmd(c.ctx, "fastboot", args)
			return err
		}
	}
	return errors.Reason("cannot find '" + partition + "' image").Err()
}

func (c *FlashOsCommand) flashAll() error {
	for _, f := range c.svc.OS.ImagePath.Files {
		if strings.HasSuffix(f, ".zip") {
			dut := c.svc.DUT
			provisionDir := c.svc.OS.ImagePath.DutAndroidProductOut
			tmpDir := filepath.Join(c.svc.OS.ImagePath.DutAndroidProductOut, "/tmp")
			dut.AssociatedHost.CreateDirectories(c.ctx, []string{tmpDir})
			args := []string{"-s", dut.SerialNumber, "update", filepath.Join(provisionDir, f)}
			// fastboot fails if TMPDIR does not point to a directory in stateful_partition.
			_, err := dut.AssociatedHost.RunCmd(c.ctx, "TMPDIR="+tmpDir+" fastboot", args)
			return err
		}
	}
	return errors.Reason("cannot find update zip file").Err()
}

func (c *FlashOsCommand) fetchOSInfo() error {
	dut := c.svc.DUT
	buildId, err := getOSBuildId(c.ctx, dut)
	if err != nil {
		return err
	}
	incrementalVersion, err := getOSIncrementalVersion(c.ctx, dut)
	if err != nil {
		return err
	}
	osVersion, err := getOSVersion(c.ctx, dut)
	if err != nil {
		return err
	}
	c.svc.OS.UpdatedBuildInfo = &service.OsBuildInfo{
		Id:                 buildId,
		IncrementalVersion: incrementalVersion,
		OsVersion:          osVersion,
	}
	return nil
}
