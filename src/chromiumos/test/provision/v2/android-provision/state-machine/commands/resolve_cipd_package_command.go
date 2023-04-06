// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"fmt"
	"log"
	"path/filepath"
	"strings"

	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"

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
		if cipdPkg.PackageProto.GetName() == "" {
			// CIPD package name is not specified in the provision request.
			// It will be resolved from the Android package name.
			// e.g. "com.google.android.gms" -> "chromiumos/infra/skylab/third_party/gmscore/gmscore_prodsc_arm64_alldpi_release_apk"
			if err := c.resolvePackageName(cipdPkg.PackageProto); err != nil {
				log.Printf("ResolveCIPDPackageCommand Failure: %v", err)
				return err
			}
		}
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

func (c *ResolveCIPDPackageCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_CIPD_PACKAGE_LOOKUP_FAILED
}

// getPackageName uses AndroidPackage proto for CIPD package resolution.
func (c *ResolveCIPDPackageCommand) resolvePackageName(cipdPackageProto *api.CIPDPackage) error {
	switch p := cipdPackageProto.GetAndroidPackage(); p {
	case api.AndroidPackage_GMS_CORE:
		var osVersion string
		if os := c.svc.OS; os != nil && os.UpdatedBuildInfo != nil {
			osVersion = os.UpdatedBuildInfo.OsVersion
		}
		if osVersion == "" {
			// Read OS version from DUT.
			v, err := getOSVersion(c.ctx, c.svc.DUT)
			if err != nil {
				return err
			}
			osVersion = v
		}
		platform := common.OSVersionToGMSCorePlatformMap[osVersion]
		if platform == "" {
			return errors.Reason("missing GMSCore package platform for Android OS v.%s", osVersion).Err()
		}
		dpi := "alldpi"
		if apkDetails := cipdPackageProto.GetApkDetails(); apkDetails != nil {
			if apkDetails.GetDensity() == api.ApkDetails_XXHDPI {
				dpi = "xxhdpi"
			}
		}
		cipdPackageProto.Name = filepath.Join(common.GMSCoreCIPDPath, fmt.Sprintf("gmscore_%s_arm64_%s_release_apk", platform, dpi))
	default:
		return errors.Reason("failed to resolve CIPD package from unsupported Android package: %s", p.String()).Err()
	}
	return nil
}
