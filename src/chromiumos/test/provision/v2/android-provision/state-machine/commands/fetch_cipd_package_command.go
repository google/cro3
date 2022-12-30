// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"fmt"
	"log"
	"path/filepath"

	"go.chromium.org/chromiumos/config/go/test/api"

	"chromiumos/test/provision/v2/android-provision/common/cipd"
	"chromiumos/test/provision/v2/android-provision/service"
)

type FetchCIPDPackageCommand struct {
	ctx  context.Context
	svc  *service.AndroidService
	cipd cipd.CIPDClient
}

func NewFetchCIPDPackageCommand(ctx context.Context, svc *service.AndroidService) *FetchCIPDPackageCommand {
	return &FetchCIPDPackageCommand{
		ctx:  ctx,
		svc:  svc,
		cipd: cipd.NewCIPDClient(ctx),
	}
}

func (c *FetchCIPDPackageCommand) Execute(log *log.Logger) error {
	log.Printf("Start FetchCIPDPackageCommand Execute")
	for _, pkg := range c.svc.ProvisionPackages {
		cipdPkg, androidPkg := pkg.CIPDPackage, pkg.AndroidPackage
		if androidPkg != nil && cipdPkg.VersionCode != androidPkg.VersionCode {
			switch p := cipdPkg.PackageProto.GetAndroidPackage(); p {
			case api.AndroidPackage_GMS_CORE:
				cipdPkg.FilePath = filepath.Join(c.svc.ProvisionDir, filepath.Base(cipdPkg.PackageName)+".zip")
			default:
				err := fmt.Errorf("unsupported Android package: %s", p.String())
				log.Printf("FetchCIPDPackageCommand Failure: %v", err)
				return err
			}
			if err := c.cipd.FetchInstanceTo(cipdPkg.PackageProto, cipdPkg.PackageName, cipdPkg.InstanceId, cipdPkg.FilePath); err != nil {
				log.Printf("FetchCIPDPackageCommand Failure: %v", err)
				return err
			}
		}
	}
	log.Printf("FetchCIPDPackageCommand Success")
	return nil
}

func (c *FetchCIPDPackageCommand) Revert() error {
	return nil
}

func (c *FetchCIPDPackageCommand) GetErrorMessage() string {
	return "failed to fetch CIPD package"
}

func (c *FetchCIPDPackageCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_CIPD_PACKAGE_FETCH_FAILED
}
