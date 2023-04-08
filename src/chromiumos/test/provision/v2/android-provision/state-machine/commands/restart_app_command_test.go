// Copyright 2023 The ChromiumOS Authors.
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

func TestRestartAppCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("RestartAppCommand", t, func() {
		associatedHost := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
		svc, _ := service.NewAndroidServiceFromExistingConnection(
			associatedHost,
			"dutSerialNumber",
			nil,
			[]*api.CIPDPackage{{}},
		)
		provisionPkg := svc.ProvisionPackages[0]
		provisionPkg.APKFile = &service.PkgFile{
			Name:    "apkName.apk",
			GsPath:  "gs_path",
			DutPath: "/tmp/instanceId/apkName.apk",
		}
		provisionPkg.AndroidPackage = &service.AndroidPackage{
			PackageName: common.GMSCorePackageName,
		}
		provisionDir, _ := os.MkdirTemp("", "testCleanup")
		defer os.RemoveAll(provisionDir)

		cmd := NewRestartAppCommand(context.Background(), svc)

		Convey("Execute", func() {
			provisionPkg.AndroidPackage.UpdatedVersionCode = "224312037"
			log, _ := common.SetUpLog(provisionDir)
			gomock.InOrder(
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("adb"), gomock.Eq([]string{"-s", "dutSerialNumber", "shell", "am", "force-stop", "com.google.android.gms"})).Return("", nil).Times(1),
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("adb"), gomock.Eq([]string{"-s", "dutSerialNumber", "shell", "am", "broadcast", "-a", "com.google.android.gms.INITIALIZE"})).Return("", nil).Times(1),
			)
			So(cmd.Execute(log), ShouldBeNil)
		})
		Convey("Execute - nothing installed", func() {
			provisionPkg.AndroidPackage.UpdatedVersionCode = ""
			log, _ := common.SetUpLog(provisionDir)
			associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Any(), gomock.Any()).Times(0)
			So(cmd.Execute(log), ShouldBeNil)
		})
		Convey("Revert", func() {
			So(cmd.Revert(), ShouldBeNil)
		})
		Convey("GetErrorMessage", func() {
			So(cmd.GetErrorMessage(), ShouldEqual, "failed to restart application")
		})
		Convey("GetStatus", func() {
			So(cmd.GetStatus(), ShouldEqual, api.InstallResponse_STATUS_POST_PROVISION_SETUP_FAILED)
		})
	})
}
