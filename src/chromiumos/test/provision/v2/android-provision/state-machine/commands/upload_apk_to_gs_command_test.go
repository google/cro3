// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/common/gsstorage"
	"chromiumos/test/provision/v2/android-provision/service"

	"github.com/golang/mock/gomock"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/chromiumos/config/go/test/api"
)

func TestUploadApkToGsCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("UploadApkToGsCommand", t, func() {
		pkgProto := &api.CIPDPackage{
			Name: "cipd_path/cipd_package_name",
			VersionOneof: &api.CIPDPackage_InstanceId{
				InstanceId: "instanceId",
			},
			AndroidPackage: api.AndroidPackage_GMS_CORE,
		}
		svc, _ := service.NewAndroidServiceFromExistingConnection(
			nil,
			"",
			[]*api.CIPDPackage{pkgProto},
		)
		// Default apkName.
		apkName := "gmscore_prodrvc_arm64_alldpi_release.apk"
		// Create provision dir and cleanup.
		provisionDir, _ := os.MkdirTemp("", "testCleanup")
		defer os.RemoveAll(provisionDir)
		// Create InstanceId dir.
		d := filepath.Join(provisionDir, "instanceId")
		err := os.Mkdir(d, 0755)
		if err != nil {
			t.Fatalf("TestUploadApkToGsCommand Failure: %v", err)
		}
		apkPath := filepath.Join(d, apkName)
		// Create apk file.
		_, err = os.Create(apkPath)
		if err != nil {
			t.Fatalf("TestUploadApkToGsCommand Failure: %v", err)
		}
		svc.ProvisionDir = provisionDir
		provisionPkg := svc.ProvisionPackages[0]
		cipdPkg := &service.CIPDPackage{
			PackageProto: pkgProto,
			FilePath:     filepath.Join(provisionDir, "/instanceId/cipd_package_name.zip"),
			PackageName:  "cipd_package_name",
			InstanceId:   "instanceId",
			VersionCode:  "1234567890",
		}
		provisionPkg.CIPDPackage = cipdPkg
		mockGsClient := gsstorage.NewMockgsClient(ctrl)
		cmd := NewUploadAPKToGSCommand(context.Background(), svc)
		cmd.gs = mockGsClient
		Convey("Execute", func() {
			log, _ := common.SetUpLog(provisionDir)
			Convey("Upload Android package", func() {
				gsPath := "gs://android-provisioning-apks/instanceId/" + apkName
				mockGsClient.EXPECT().Upload(gomock.Eq(context.Background()), gomock.Eq(apkPath), gomock.Eq("instanceId/"+apkName)).Return(nil).Times(1)
				So(cmd.Execute(log), ShouldBeNil)
				So(provisionPkg.APKFile.Name, ShouldEqual, apkName)
				So(provisionPkg.APKFile.GsPath, ShouldEqual, gsPath)
			})
		})
		Convey("Revert", func() {
			So(cmd.Revert(), ShouldBeNil)
		})
		Convey("GetErrorMessage", func() {
			So(cmd.GetErrorMessage(), ShouldEqual, "failed to extract APK file")
		})
		Convey("GetStatus", func() {
			So(cmd.GetStatus(), ShouldEqual, api.InstallResponse_STATUS_GS_UPLOAD_FAILED)
		})
	})
}
