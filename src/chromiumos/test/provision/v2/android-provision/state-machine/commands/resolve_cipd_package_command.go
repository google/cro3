// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"fmt"
	"log"
	"strings"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/common/cipd"
	"chromiumos/test/provision/v2/android-provision/service"
)

type ResolveCIPDPackageCommand struct {
	ctx  context.Context
	svc  *service.AndroidService
	cipd cipd.CIPDClient
}

func NewResolveCIPDPackageCommand(ctx context.Context, svc *service.AndroidService) *ResolveCIPDPackageCommand {
	return &ResolveCIPDPackageCommand{
		ctx:  ctx,
		svc:  svc,
		cipd: cipd.NewCIPDClient(ctx),
	}
}

func (c *ResolveCIPDPackageCommand) Execute(log *log.Logger) error {
	log.Printf("Start ResolveCIPDPackageCommand Execute")
	for _, pkg := range c.svc.ProvisionPackages {
		cipdPkg := pkg.CIPDPackage
		d, err := c.cipd.Describe(cipdPkg.PackageProto, true, false)
		if err != nil {
			log.Printf("ResolveCIPDPackageCommand Failure: %v", err)
			return err
		}
		var versionCodeTag string
		for _, t := range d.Tags {
			if s := strings.SplitN(t.Tag, ":", 2); s[0] == common.CIPDVersionCodeTagName {
				versionCodeTag = s[1]
				break
			}
		}
		if versionCodeTag == "" {
			err = fmt.Errorf("%s tag is empty or does not exist", common.CIPDVersionCodeTagName)
			log.Printf("ResolveCIPDPackageCommand Failure: %v", err)
			return err
		}
		cipdPkg.PackageName = d.InstanceInfo.Pin.PackageName
		cipdPkg.InstanceId = d.InstanceInfo.Pin.InstanceID
		cipdPkg.VersionCode = versionCodeTag
	}
	log.Printf("ResolveCIPDPackageCommand Success")
	return nil
}

func (c *ResolveCIPDPackageCommand) Revert() error {
	return nil
}

func (c *ResolveCIPDPackageCommand) GetErrorMessage() string {
	return "failed to resolve CIPD package"
}
