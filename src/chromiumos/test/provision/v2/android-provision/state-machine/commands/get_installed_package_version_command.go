// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"fmt"
	"log"
	"regexp"
	"strings"

	"go.chromium.org/chromiumos/config/go/test/api"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/service"
)

type GetInstalledPackageVersionCommand struct {
	ctx context.Context
	svc *service.AndroidService
}

func NewGetInstalledPackageVersionCommand(ctx context.Context, svc *service.AndroidService) *GetInstalledPackageVersionCommand {
	return &GetInstalledPackageVersionCommand{
		ctx: ctx,
		svc: svc,
	}
}

func (c *GetInstalledPackageVersionCommand) Execute(log *log.Logger) error {
	log.Printf("Start GetInstalledPackageVersionCommand Execute")
	for _, pkg := range c.svc.ProvisionPackages {
		var packageName string
		switch p := pkg.CIPDPackage.PackageProto.GetAndroidPackage(); p {
		case api.AndroidPackage_GMS_CORE:
			packageName = common.GMSCorePackageName
		default:
			err := fmt.Errorf("unsupported Android package: %s", p.String())
			log.Printf("GetInstalledPackageVersionCommand Failure: %v", err)
			return err
		}
		dut := c.svc.DUT
		versionCode, err := getAndroidPackageVersionCode(c.ctx, dut, packageName)
		if err != nil {
			log.Printf("GetInstalledPackageVersionCommand start failed: %v", err)
			return err
		}
		pkg.AndroidPackage = &service.AndroidPackage{
			PackageName: packageName,
			VersionCode: versionCode,
		}
	}
	log.Printf("GetInstalledPackageVersionCommand Success")
	return nil
}

func getAndroidPackageVersionCode(ctx context.Context, dut *service.DUTConnection, packageName string) (string, error) {
	re := regexp.MustCompile(`^versionCode=(\d+).+`)
	args := []string{"-s", dut.SerialNumber, "shell", "dumpsys", "package", packageName, "|", "grep", "versionCode", "|", "sort", "-r", "|", "head", "-n", "1"}
	out, err := dut.AssociatedHost.RunCmd(ctx, "adb", args)
	if err != nil {
		return "", err
	}
	return re.ReplaceAllString(strings.TrimSpace(out), "$1"), nil
}

func (c *GetInstalledPackageVersionCommand) Revert() error {
	return nil
}

func (c *GetInstalledPackageVersionCommand) GetErrorMessage() string {
	return "failed to read installed package version"
}

func (c *GetInstalledPackageVersionCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_DUT_UNREACHABLE_PRE_PROVISION
}
