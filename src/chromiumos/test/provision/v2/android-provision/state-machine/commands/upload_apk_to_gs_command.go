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
		gs:  gsstorage.NewGsClient(),
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
			apkName, err := getApkName(cipdPkg.PackageProto)
			if err != nil {
				log.Printf("UploadAPKToGSCommand Failure: %v", err)
				return err
			}
			apkPath := filepath.Join(dstPath, apkName)
			if _, err := os.Stat(apkPath); os.IsNotExist(err) {
				err = fmt.Errorf("APK file is missing from CIPD package: %s", apkName)
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

func getApkName(cipdPkgProto *api.CIPDPackage) (string, error) {
	switch p := cipdPkgProto.GetAndroidPackage(); p {
	case api.AndroidPackage_GMS_CORE:
		return getGmsCoreApkName(cipdPkgProto.GetApkDetails())
	default:
		return "", fmt.Errorf("unsupported Android package: %s", p.String())
	}
}

func getGmsCoreApkName(apkDetails *api.ApkDetails) (string, error) {
	var arch, bt, dpi, bp string
	switch archEnum := apkDetails.GetArchitecture(); archEnum {
	case api.ApkDetails_ARM64, api.ApkDetails_ARCHITECTURE_UNSPECIFIED:
		arch = "arm64"
	case api.ApkDetails_X86_64:
		arch = "x86_64"
	case api.ApkDetails_ARMV7:
		arch = "arm7"
	case api.ApkDetails_X86:
		arch = "x86"
	default:
		return "", fmt.Errorf("unsupported APK architecture: %s", archEnum.String())
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
	case api.ApkDetails_PHONE_RVC, api.ApkDetails_BUILD_TYPE_UNSPECIFIED:
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
		return "", fmt.Errorf("unsupported APK build type: %s", btEnum.String())
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
		dpi = "alldpi"
	default:
		return "", fmt.Errorf("unsupported APK density: %s", dpiEnum.String())
	}
	switch bpEnum := apkDetails.GetBuildPurpose(); bpEnum {
	case api.ApkDetails_RAW:
		bp = "raw"
	case api.ApkDetails_RELEASE, api.ApkDetails_BUILD_PURPOSE_UNSPECIFIED:
		bp = "release"
	case api.ApkDetails_DEBUG:
		bp = "debug"
	case api.ApkDetails_DEBUG_SHRUNK:
		bp = "debug_shrunk"
	default:
		return "", fmt.Errorf("unsupported APK build purpose: %s", bpEnum.String())
	}
	return fmt.Sprintf("gmscore_%s_%s_%s_%s.apk", bt, arch, dpi, bp), nil
}
