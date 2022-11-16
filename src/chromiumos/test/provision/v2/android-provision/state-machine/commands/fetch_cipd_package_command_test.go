// Copyright 2022 The ChromiumOS Authors.
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
	"chromiumos/test/provision/v2/android-provision/common/cipd"
	"chromiumos/test/provision/v2/android-provision/service"
)

func TestFetchCIPDPackageCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("FetchCIPDPackageCommand", t, func() {
		pkgProto := &api.CIPDPackage{
			Name: "cipd_path/cipd_package_name",
			VersionOneof: &api.CIPDPackage_InstanceId{
				InstanceId: "instanceId",
			},
			AndroidPackage: api.AndroidPackage_GMS_CORE,
		}
		cipdPkg := &service.CIPDPackage{
			PackageProto: pkgProto,
			PackageName:  "cipd_package_name",
			InstanceId:   "instanceId",
			VersionCode:  "1234567890",
		}
		androidPkg := &service.AndroidPackage{
			PackageName: "android.package.name",
		}
		svc, _ := service.NewAndroidServiceFromExistingConnection(
			nil,
			"",
			[]*api.CIPDPackage{pkgProto},
		)
		provisionPkg := svc.ProvisionPackages[0]
		provisionPkg.CIPDPackage = cipdPkg
		provisionPkg.AndroidPackage = androidPkg
		provisionDir, _ := os.MkdirTemp("", "testCleanup")
		defer os.RemoveAll(provisionDir)
		svc.ProvisionDir = "/tmp/provision_dir"

		cmd := NewFetchCIPDPackageCommand(context.Background(), svc)

		Convey("Execute", func() {
			log, _ := common.SetUpLog(provisionDir)
			mockCIPDClient := cipd.NewMockCIPDClientInterface(ctrl)
			cmd.cipd = mockCIPDClient
			provisionPkg.CIPDPackage.PackageProto.AndroidPackage = api.AndroidPackage_GMS_CORE
			Convey("New Android Package", func() {
				provisionPkg.AndroidPackage.VersionCode = ""
				mockCIPDClient.EXPECT().FetchInstanceTo(gomock.Eq(pkgProto), gomock.Eq("cipd_package_name"), gomock.Eq("instanceId"), gomock.Eq("/tmp/provision_dir/cipd_package_name.zip")).Times(1)
				So(cmd.Execute(log), ShouldBeNil)
			})
			Convey("Existing Android Package - same version code", func() {
				provisionPkg.AndroidPackage.VersionCode = "1234567890"
				mockCIPDClient.EXPECT().FetchInstanceTo(gomock.Eq(pkgProto), gomock.Eq("cipd_package_name"), gomock.Eq("instanceId"), gomock.Eq("/tmp/provision_dir/cipd_package_name.zip")).Times(0)
				So(cmd.Execute(log), ShouldBeNil)
			})
			Convey("Existing Android Package - different version code", func() {
				provisionPkg.AndroidPackage.VersionCode = "1234567889"
				mockCIPDClient.EXPECT().FetchInstanceTo(gomock.Eq(pkgProto), gomock.Eq("cipd_package_name"), gomock.Eq("instanceId"), gomock.Eq("/tmp/provision_dir/cipd_package_name.zip")).Times(1)
				So(cmd.Execute(log), ShouldBeNil)
			})
			Convey("Unknown Android Package type - returns error", func() {
				provisionPkg.AndroidPackage.VersionCode = ""
				provisionPkg.CIPDPackage.PackageProto.AndroidPackage = api.AndroidPackage_ANDROID_PACKAGE_UNSPECIFIED
				mockCIPDClient.EXPECT().FetchInstanceTo(gomock.Eq(pkgProto), gomock.Eq("cipd_package_name"), gomock.Eq("instanceId"), gomock.Eq("/tmp/provision_dir/cipd_package_name.zip")).Times(0)
				So(cmd.Execute(log), ShouldNotBeNil)
			})
		})
		Convey("Revert", func() {
			So(cmd.Revert(), ShouldBeNil)
		})
		Convey("GetErrorMessage", func() {
			So(cmd.GetErrorMessage(), ShouldEqual, "failed to fetch CIPD package")
		})
	})
}
