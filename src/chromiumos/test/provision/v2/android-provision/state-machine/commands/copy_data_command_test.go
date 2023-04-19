// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"os"
	"testing"

	"github.com/golang/mock/gomock"
	"go.chromium.org/chromiumos/config/go/test/api"

	. "github.com/smartystreets/goconvey/convey"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/common/gsstorage"
	"chromiumos/test/provision/v2/android-provision/service"
	mock_common_utils "chromiumos/test/provision/v2/mock-common-utils"
)

func TestCopyDataCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("CopyDataCommand", t, func() {
		associatedHost := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
		pkgProto := &api.CIPDPackage{
			Name: "cipd_path/cipd_package_name",
			VersionOneof: &api.CIPDPackage_InstanceId{
				InstanceId: "instanceId",
			},
			AndroidPackage: api.AndroidPackage_GMS_CORE,
		}
		apkFile := &service.PkgFile{
			Name:   "apkName.apk",
			GsPath: "gsPath",
		}
		svc, _ := service.NewAndroidServiceFromExistingConnection(
			associatedHost,
			"dutSerialNumber",
			nil,
			[]*api.CIPDPackage{pkgProto},
		)
		provisionPkg := svc.ProvisionPackages[0]
		provisionPkg.CIPDPackage.InstanceId = "instanceId"
		provisionPkg.CIPDPackage.VersionCode = "versionCode"
		provisionPkg.APKFile = apkFile
		provisionDir, _ := os.MkdirTemp("", "testCleanup")
		defer os.RemoveAll(provisionDir)
		svc.OS = &service.AndroidOS{
			ImagePath: &service.ImagePath{
				DutAndroidProductOut: "dutProvisionDir",
			}}
		mockGsClient := gsstorage.NewMockGsClient(ctrl)
		cmd := NewCopyDataCommand(context.Background(), svc)
		cmd.gs = mockGsClient

		Convey("Execute - copy package", func() {
			log, _ := common.SetUpLog(provisionDir)
			cmd.ctx = context.WithValue(cmd.ctx, "stage", common.PackageFetch)
			gomock.InOrder(
				associatedHost.EXPECT().CopyData(gomock.Any(), "gsPath", "/tmp/instanceId/apkName.apk").Times(1),
			)
			So(provisionPkg.APKFile.DutPath, ShouldBeEmpty)
			So(cmd.Execute(log), ShouldBeNil)
			So(provisionPkg.APKFile.DutPath, ShouldEqual, "/tmp/instanceId/apkName.apk")
		})
		Convey("Execute - copy os images from folder", func() {
			svc.OS.ImagePath.GsPath = "gs://bucket/folder1/folder2/"
			cmd.ctx = context.WithValue(cmd.ctx, "stage", common.OSFetch)
			log, _ := common.SetUpLog(provisionDir)
			mockGsClient.EXPECT().ListFiles(gomock.Any(), gomock.Eq("folder1/folder2/"), gomock.Eq("/")).Return([]string{"bootloader.img", "radio.img", "smtg-img-2132123.zip"}, nil).Times(1)
			associatedHost.EXPECT().CopyData(gomock.Any(), gomock.Any(), gomock.Eq("/mnt/stateful_partition/android_provision/folder1/folder2/bootloader.img")).Times(1)
			associatedHost.EXPECT().CopyData(gomock.Any(), gomock.Any(), gomock.Eq("/mnt/stateful_partition/android_provision/folder1/folder2/radio.img")).Times(1)
			associatedHost.EXPECT().CopyData(gomock.Any(), gomock.Any(), gomock.Eq("/mnt/stateful_partition/android_provision/folder1/folder2/smtg-img-2132123.zip")).Times(1)
			So(cmd.Execute(log), ShouldBeNil)
			So(svc.OS.ImagePath.Files, ShouldResemble, []string{"bootloader.img", "radio.img", "smtg-img-2132123.zip"})
		})
		Convey("Execute - undefined stage", func() {
			cmd.ctx = context.WithValue(cmd.ctx, "stage", nil)
			log, _ := common.SetUpLog(provisionDir)
			So(cmd.Execute(log), ShouldBeError)
		})
		Convey("Revert", func() {
			So(cmd.Revert(), ShouldBeNil)
		})
		Convey("GetErrorMessage", func() {
			So(cmd.GetErrorMessage(), ShouldEqual, "failed to copy data")
		})
		Convey("GetStatus", func() {
			So(cmd.GetStatus(), ShouldEqual, api.InstallResponse_STATUS_GS_DOWNLOAD_FAILED)
		})
	})
}
