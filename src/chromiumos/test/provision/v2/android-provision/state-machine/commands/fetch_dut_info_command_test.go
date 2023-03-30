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

func TestFetchDutInfoCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("FetchDutInfoCommand", t, func() {
		associatedHost := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
		pkgProto := &api.CIPDPackage{
			AndroidPackage: api.AndroidPackage_GMS_CORE,
		}
		svc, _ := service.NewAndroidServiceFromExistingConnection(
			associatedHost,
			"dutSerialNumber",
			&api.AndroidOsImage{LocationOneof: &api.AndroidOsImage_OsVersion{OsVersion: "10"}},
			[]*api.CIPDPackage{pkgProto},
		)
		provisionDir, _ := os.MkdirTemp("", "testCleanup")
		defer os.RemoveAll(provisionDir)

		cmd := NewFetchDutInfoCommand(context.Background(), svc)

		Convey("Execute", func() {
			log, _ := common.SetUpLog(provisionDir)
			boardArgs := []string{"-s", "dutSerialNumber", "shell", "getprop", "ro.product.board"}
			buildIdArgs := []string{"-s", "dutSerialNumber", "shell", "getprop", "ro.build.id"}
			versionArgs := []string{"-s", "dutSerialNumber", "shell", "getprop", "ro.build.version.release"}
			incrVersionArgs := []string{"-s", "dutSerialNumber", "shell", "getprop", "ro.build.version.incremental"}
			pkgArgs := []string{"-s", "dutSerialNumber", "shell", "dumpsys", "package", common.GMSCorePackageName, "|", "grep", "versionCode", "|", "sort", "-r", "|", "head", "-n", "1"}
			gomock.InOrder(
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("adb"), boardArgs).Return("board.Value", nil).Times(1),
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("adb"), buildIdArgs).Return("buildId.Value", nil).Times(1),
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("adb"), versionArgs).Return("12", nil).Times(1),
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("adb"), incrVersionArgs).Return("1234567890", nil).Times(1),
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("adb"), pkgArgs).Return("versionCode=224312037 minSdk=30 targetSdk=33", nil).Times(1),
			)
			expectedBoard := "board.Value"
			expectedBuildInfo := &service.OsBuildInfo{
				Id:                 "buildId.Value",
				OsVersion:          "12",
				IncrementalVersion: "1234567890",
			}
			expectedAndroidPkg := &service.AndroidPackage{
				PackageName: common.GMSCorePackageName,
				VersionCode: "224312037",
			}
			So(cmd.Execute(log), ShouldBeNil)
			So(svc.DUT.Board, ShouldEqual, expectedBoard)
			So(svc.OS.BuildInfo, ShouldResemble, expectedBuildInfo)
			So(svc.ProvisionPackages[0].AndroidPackage, ShouldResemble, expectedAndroidPkg)
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
