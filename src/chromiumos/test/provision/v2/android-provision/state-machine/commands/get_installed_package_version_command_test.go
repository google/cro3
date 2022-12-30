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
	"chromiumos/test/provision/v2/android-provision/service"
	mock_common_utils "chromiumos/test/provision/v2/mock-common-utils"
)

func TestGetInstalledPackageVersionCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("GetInstalledPackageVersionCommand", t, func() {
		associatedHost := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
		pkgProto := &api.CIPDPackage{
			AndroidPackage: api.AndroidPackage_GMS_CORE,
		}
		svc, _ := service.NewAndroidServiceFromExistingConnection(
			associatedHost,
			"dutSerialNumber",
			[]*api.CIPDPackage{pkgProto},
		)
		provisionPkg := svc.ProvisionPackages[0]
		provisionDir, _ := os.MkdirTemp("", "testCleanup")
		defer os.RemoveAll(provisionDir)

		cmd := NewGetInstalledPackageVersionCommand(context.Background(), svc)

		Convey("Execute", func() {
			log, _ := common.SetUpLog(provisionDir)
			args := []string{"-s", "dutSerialNumber", "shell", "dumpsys", "package", common.GMSCorePackageName, "|", "grep", "versionCode", "|", "sort", "-r", "|", "head", "-n", "1"}
			associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("adb"), args).Return("versionCode=224312037 minSdk=30 targetSdk=33", nil).Times(1)
			expectedAndroidPkg := &service.AndroidPackage{
				PackageName: common.GMSCorePackageName,
				VersionCode: "224312037",
			}
			So(cmd.Execute(log), ShouldBeNil)
			So(provisionPkg.AndroidPackage, ShouldResemble, expectedAndroidPkg)
		})
		Convey("Revert", func() {
			So(cmd.Revert(), ShouldBeNil)
		})
		Convey("GetErrorMessage", func() {
			So(cmd.GetErrorMessage(), ShouldEqual, "failed to read installed package version")
		})
		Convey("GetStatus", func() {
			So(cmd.GetStatus(), ShouldEqual, api.InstallResponse_STATUS_DUT_UNREACHABLE_PRE_PROVISION)
		})
	})
}
