// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"

	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"
	"google.golang.org/api/googleapi"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/common/gsstorage"
	"chromiumos/test/provision/v2/android-provision/service"
)

type UploadAPKToGSCommand struct {
	ctx context.Context
	svc *service.AndroidService
	gs  gsstorage.GsClient
}

func NewUploadAPKToGSCommand(ctx context.Context, svc *service.AndroidService) *UploadAPKToGSCommand {
	return &UploadAPKToGSCommand{
		ctx: ctx,
		svc: svc,
		gs:  gsstorage.NewGsClient(common.GMSCorePackageName),
	}
}

func (c *UploadAPKToGSCommand) Execute(log *log.Logger) error {
	log.Printf("Start UploadAPKToGSCommand Execute")
	for _, pkg := range c.svc.ProvisionPackages {
		if cipdPkg := pkg.CIPDPackage; cipdPkg.FilePath != "" {
			dstPath := filepath.Join(c.svc.ProvisionDir, cipdPkg.InstanceId)
			if _, err := os.Stat(dstPath); os.IsNotExist(err) {
				continue
			}
			apkName, err := c.getApkName(cipdPkg.PackageProto)
			if err != nil {
				log.Printf("UploadAPKToGSCommand Failure: %v", err)
				return err
			}
			apkPath := filepath.Join(dstPath, apkName)
			if _, err = os.Stat(apkPath); os.IsNotExist(err) {
				err = errors.Reason("APK file is missing from CIPD package: %s", apkName).Err()
				log.Printf("UploadAPKToGSCommand Failure: %v", err)
				return err
			}
			apkRemotePath := cipdPkg.InstanceId + "/" + apkName
			if err := c.gs.Upload(c.ctx, apkPath, apkRemotePath); err != nil {
				switch e := err.(type) {
				case *googleapi.Error:
					// If file already exists we do nothing.
					if e.Code != http.StatusPreconditionFailed {
						log.Printf("UploadAPKToGSCommand Failure: %v", err)
						return err
					}
				default:
					log.Printf("UploadAPKToGSCommand Failure: %v", err)
					return err
				}
			}
			gspath := "gs://" + common.GSPackageBucketName + "/" + apkRemotePath
			pkg.APKFile = &service.PkgFile{
				Name:   apkName,
				GsPath: gspath,
			}
		}
	}
	log.Printf("UploadAPKToGSCommand Success")
	return nil
}

func (c *UploadAPKToGSCommand) Revert() error {
	return nil
}

func (c *UploadAPKToGSCommand) GetErrorMessage() string {
	return "failed to extract APK file"
}

func (c *UploadAPKToGSCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_GS_UPLOAD_FAILED
}

func (c *UploadAPKToGSCommand) getApkName(cipdPkgProto *api.CIPDPackage) (string, error) {
	switch p := cipdPkgProto.GetAndroidPackage(); p {
	case api.AndroidPackage_GMS_CORE:
		apkDetails := cipdPkgProto.GetApkDetails()
		if apkDetails != nil {
			archProto := apkDetails.GetArchitecture()
			buildProto := apkDetails.GetBuildType()
			if archProto != api.ApkDetails_ARCHITECTURE_UNSPECIFIED && buildProto != api.ApkDetails_BUILD_TYPE_UNSPECIFIED {
				// Resolve APK name from input proto.
				return c.getGmsCoreApkNameFromProto(apkDetails)
			}
		}
		return c.resolveGmsCoreApkName(apkDetails)
	default:
		return "", errors.Reason("unsupported Android package: %s", p.String()).Err()
	}
}

func (c *UploadAPKToGSCommand) getGmsCoreApkNameFromProto(apkDetails *api.ApkDetails) (string, error) {
	var arch, bt, dpi, bp string
	switch archEnum := apkDetails.GetArchitecture(); archEnum {
	case api.ApkDetails_ARM64:
		arch = "arm64"
	case api.ApkDetails_X86_64:
		arch = "x86_64"
	case api.ApkDetails_ARMV7:
		arch = "arm7"
	case api.ApkDetails_X86:
		arch = "x86"
	default:
		return "", errors.Reason("unsupported APK architecture: %s", archEnum.String()).Err()
	}
	switch btEnum := apkDetails.GetBuildType(); btEnum {
	case api.ApkDetails_PHONE_PRE_LMP:
		bt = "prod"
	case api.ApkDetails_PHONE_LMP:
		bt = "prodlmp"
	case api.ApkDetails_PHONE_MNC:
		bt = "prodmnc"
	case api.ApkDetails_PHONE_PI:
		bt = "prodpi"
	case api.ApkDetails_PHONE_RVC:
		bt = "prodrvc"
	case api.ApkDetails_PHONE_SC:
		bt = "prodsc"
	case api.ApkDetails_PHONE_NEXT:
		bt = "prodnext"
	case api.ApkDetails_PHONE_GO:
		bt = "prodgo"
	case api.ApkDetails_PHONE_GO_R:
		bt = "prodgor"
	case api.ApkDetails_PHONE_GO_S:
		bt = "prodgos"
	default:
		return "", errors.Reason("unsupported APK build type: %s", btEnum.String()).Err()
	}
	switch dpiEnum := apkDetails.GetDensity(); dpiEnum {
	case api.ApkDetails_MDPI:
		dpi = "mdpi"
	case api.ApkDetails_HDPI:
		dpi = "hdpi"
	case api.ApkDetails_XHDPI:
		dpi = "xhdpi"
	case api.ApkDetails_XXHDPI:
		dpi = "xxhdpi"
	case api.ApkDetails_ALLDPI, api.ApkDetails_DENSITY_UNSPECIFIED:
		// Default value.
		dpi = "alldpi"
	default:
		return "", errors.Reason("unsupported APK density: %s", dpiEnum.String()).Err()
	}
	switch bpEnum := apkDetails.GetBuildPurpose(); bpEnum {
	case api.ApkDetails_RAW:
		bp = "raw"
	case api.ApkDetails_RELEASE, api.ApkDetails_BUILD_PURPOSE_UNSPECIFIED:
		// Default value.
		bp = "release"
	case api.ApkDetails_DEBUG:
		bp = "debug"
	case api.ApkDetails_DEBUG_SHRUNK:
		bp = "debug_shrunk"
	default:
		return "", errors.Reason("unsupported APK build purpose: %s", bpEnum.String()).Err()
	}
	return fmt.Sprintf("gmscore_%s_%s_%s_%s.apk", bt, arch, dpi, bp), nil
}

func (c *UploadAPKToGSCommand) resolveGmsCoreApkName(apkDetails *api.ApkDetails) (string, error) {
	var osVersion string
	if os := c.svc.OS; os != nil && os.UpdatedBuildInfo != nil {
		osVersion = os.UpdatedBuildInfo.OsVersion
	}
	if osVersion == "" {
		// Read OS version from DUT.
		v, err := getOSVersion(c.ctx, c.svc.DUT)
		if err != nil {
			return "", err
		}
		osVersion = v
	}
	platform := common.OSVersionToGMSCorePlatformMap[osVersion]
	if platform == "" {
		return "", errors.Reason("missing GMSCore package platform for Android OS v.%s", osVersion).Err()
	}
	dpi := "alldpi"
	if apkDetails != nil && apkDetails.GetDensity() == api.ApkDetails_XXHDPI {
		dpi = "xxhdpi"
	}
	return fmt.Sprintf("gmscore_%s_arm64_%s_release.apk", platform, dpi), nil
}
