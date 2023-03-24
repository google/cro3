// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"os"
	"testing"

	mock_common_utils "chromiumos/test/provision/v2/mock-common-utils"
	"github.com/golang/mock/gomock"
	"go.chromium.org/chromiumos/config/go/test/api"

	. "github.com/smartystreets/goconvey/convey"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/common/zip"
	"chromiumos/test/provision/v2/android-provision/service"
)

func TestExtractZipCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("ExtractZipCommand", t, func() {
		pkgProto := &api.CIPDPackage{
			Name: "cipd_path/cipd_package_name",
			VersionOneof: &api.CIPDPackage_InstanceId{
				InstanceId: "instanceId",
			},
			AndroidPackage: api.AndroidPackage_GMS_CORE,
		}
		cipdPkg := &service.CIPDPackage{
			PackageProto: pkgProto,
			FilePath:     "/tmp/instanceId/cipd_package_name.zip",
			PackageName:  "cipd_package_name",
			InstanceId:   "instanceId",
			VersionCode:  "1234567890",
		}
		associatedHost := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
		svc, _ := service.NewAndroidServiceFromExistingConnection(
			associatedHost,
			"",
			nil,
			[]*api.CIPDPackage{pkgProto},
		)
		provisionPkg := svc.ProvisionPackages[0]
		provisionPkg.CIPDPackage = cipdPkg
		provisionDir, _ := os.MkdirTemp("", "testCleanup")
		defer os.RemoveAll(provisionDir)
		svc.ProvisionDir = provisionDir
		svc.OS = &service.AndroidOS{
			ImagePath: &service.ImagePath{
				DutAndroidProductOut: "dutProvisionDir",
			}}
		ctx := context.Background()
		cmd := NewExtractZipCommand(ctx, svc)

		Convey("Execute - OSFetch", func() {
			svc.OS.ImagePath.GsPath = "gs://bucket/folder/image.zip"
			cmd.ctx = context.WithValue(cmd.ctx, "stage", common.OSFetch)
			log, _ := common.SetUpLog(provisionDir)
			files := "bootloader.img radio.img update.zip"

			infoArgs := []string{"-1", "dutProvisionDir/image.zip", "|", "grep", "-E", "'\\.(img|zip)$'", "|", "awk", "'{print}'", "ORS=' '"}
			unzipArgs := []string{"-oq", "dutProvisionDir/image.zip", files, "-d", "dutProvisionDir"}
			gomock.InOrder(
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("zipinfo"), gomock.Eq(infoArgs)).Return(files, nil).Times(1),
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("unzip"), gomock.Eq(unzipArgs)).Return("", nil).Times(1),
			)
			So(cmd.Execute(log), ShouldBeNil)
			So(svc.OS.ImagePath.Files, ShouldResemble, []string{"bootloader.img", "radio.img", "update.zip"})
		})
		Convey("Execute - OSFetch - No zip file", func() {
			svc.OS.ImagePath.GsPath = ""
			cmd.ctx = context.WithValue(cmd.ctx, "stage", common.OSFetch)
			log, _ := common.SetUpLog(provisionDir)

			associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("zipinfo"), gomock.Any()).Times(0)
			associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("unzip"), gomock.Any()).Times(0)
			So(cmd.Execute(log), ShouldBeNil)
			So(svc.OS.ImagePath.Files, ShouldBeEmpty)
		})
		Convey("Execute - OSFetch - No image files", func() {
			svc.OS.ImagePath.GsPath = "gs://bucket/folder/image.zip"
			cmd.ctx = context.WithValue(cmd.ctx, "stage", common.OSFetch)
			log, _ := common.SetUpLog(provisionDir)

			infoArgs := []string{"-1", "dutProvisionDir/image.zip", "|", "grep", "-E", "'\\.(img|zip)$'", "|", "awk", "'{print}'", "ORS=' '"}
			associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("zipinfo"), gomock.Eq(infoArgs)).Return("", nil).Times(1)
			associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("unzip"), gomock.Any()).Times(0)
			So(cmd.Execute(log), ShouldNotBeNil)
			So(svc.OS.ImagePath.Files, ShouldBeEmpty)
		})
		Convey("Execute - PackageFetch", func() {
			cmd.ctx = context.WithValue(cmd.ctx, "stage", common.PackageFetch)
			mockZipReader := zip.NewMockZipReaderInterface(ctrl)
			cmd.zip = mockZipReader
			log, _ := common.SetUpLog(provisionDir)

			mockZipReader.EXPECT().UnzipFile(gomock.Eq("/tmp/instanceId/cipd_package_name.zip"), gomock.Eq(provisionDir+"/instanceId")).Times(1)
			So(cmd.Execute(log), ShouldBeNil)
		})
		Convey("Execute - undefined stage", func() {
			cmd.ctx = context.WithValue(cmd.ctx, "stage", nil)
			log, _ := common.SetUpLog(provisionDir)
			So(cmd.Execute(log), ShouldNotBeNil)
		})
		Convey("Revert", func() {
			So(cmd.Revert(), ShouldBeNil)
		})
		Convey("GetErrorMessage", func() {
			So(cmd.GetErrorMessage(), ShouldEqual, "failed to extract zip file")
		})
		Convey("GetStatus", func() {
			So(cmd.GetStatus(), ShouldEqual, api.InstallResponse_STATUS_PRE_PROVISION_SETUP_FAILED)
		})
	})
}
