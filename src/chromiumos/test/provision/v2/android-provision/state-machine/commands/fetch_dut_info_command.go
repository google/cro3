// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"fmt"
	"log"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/service"
	"go.chromium.org/chromiumos/config/go/test/api"
)

type FetchDutInfoCommand struct {
	ctx context.Context
	svc *service.AndroidService
}

func NewFetchDutInfoCommand(ctx context.Context, svc *service.AndroidService) *FetchDutInfoCommand {
	return &FetchDutInfoCommand{
		ctx: ctx,
		svc: svc,
	}
}

func (c *FetchDutInfoCommand) Execute(log *log.Logger) error {
	log.Printf("Start FetchDutInfoCommand Execute")
	if err := c.fetchBoard(); err != nil {
		log.Printf("FetchDutInfoCommand Failure: %v", err)
		return err
	}
	if err := c.fetchOSInfo(); err != nil {
		log.Printf("FetchDutInfoCommand Failure: %v", err)
		return err
	}
	if err := c.fetchPackagesInfo(); err != nil {
		log.Printf("FetchDutInfoCommand Failure: %v", err)
		return err
	}
	log.Printf("FetchDutInfoCommand Success")
	return nil
}

func (c *FetchDutInfoCommand) Revert() error {
	return nil
}

func (c *FetchDutInfoCommand) GetErrorMessage() string {
	return "failed to read installed package version"
}

func (c *FetchDutInfoCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_DUT_UNREACHABLE_PRE_PROVISION
}

func (c *FetchDutInfoCommand) fetchBoard() error {
	dut := c.svc.DUT
	// Fetch DUT board.
	board, err := getBoard(c.ctx, dut)
	if err != nil {
		return err
	}
	c.svc.DUT.Board = board
	return nil
}

func (c *FetchDutInfoCommand) fetchOSInfo() error {
	if c.svc.OS == nil {
		// OS provision is not requested.
		return nil
	}
	dut := c.svc.DUT
	// Fetch OS build ID.
	buildId, err := getOSBuildId(c.ctx, dut)
	if err != nil {
		return err
	}
	osVersion, err := getOSVersion(c.ctx, dut)
	if err != nil {
		return err
	}
	// Fetch incremental build version.
	incrementalVersion, err := getOSIncrementalVersion(c.ctx, dut)
	if err != nil {
		return err
	}
	c.svc.OS.BuildInfo = &service.OsBuildInfo{
		Id:                 buildId,
		OsVersion:          osVersion,
		IncrementalVersion: incrementalVersion,
	}
	return nil
}

func (c *FetchDutInfoCommand) fetchPackagesInfo() error {
	dut := c.svc.DUT
	for _, pkg := range c.svc.ProvisionPackages {
		pkg.AndroidPackage = &service.AndroidPackage{}
		switch p := pkg.CIPDPackage.PackageProto.GetAndroidPackage(); p {
		case api.AndroidPackage_GMS_CORE:
			pkg.AndroidPackage.PackageName = common.GMSCorePackageName
		default:
			return fmt.Errorf("unsupported Android package: %s", p.String())
		}
		versionCode, err := getAndroidPackageVersionCode(c.ctx, dut, pkg.AndroidPackage.PackageName)
		if err != nil {
			return err
		}
		pkg.AndroidPackage.VersionCode = versionCode
	}
	return nil
}
