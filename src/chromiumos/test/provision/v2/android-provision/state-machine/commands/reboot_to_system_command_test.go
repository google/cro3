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

func TestRebootToSystemCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("RebootToSystemCommand", t, func() {
		associatedHost := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
		svc, _ := service.NewAndroidServiceFromExistingConnection(
			associatedHost,
			"dutSerialNumber",
			nil,
			nil,
		)
		provisionDir, _ := os.MkdirTemp("", "testCleanup")
		defer os.RemoveAll(provisionDir)
		log, _ := common.SetUpLog(provisionDir)
		cmd := NewRebootToSystemCommand(context.Background(), svc)

		Convey("Execute", func() {
			svc.OS = &service.AndroidOS{ImagePath: &service.ImagePath{}}
			rebootArgs := []string{"-s", "dutSerialNumber", "reboot"}
			waitArgs := []string{"devices", "|", "grep", "-sw", "dutSerialNumber", "|", "awk", "'{print $2}'"}

			gomock.InOrder(
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("fastboot"), gomock.Eq(rebootArgs)).Return("", nil).Times(1),
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("adb"), gomock.Eq(waitArgs)).Return("device", nil).Times(3),
			)
			So(cmd.Execute(log), ShouldBeNil)
		})
		Convey("Execute - Nothing to provision", func() {
			log, _ := common.SetUpLog(provisionDir)
			svc.OS = nil
			associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("fastboot"), gomock.Any()).Times(0)
			associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("adb"), gomock.Any()).Times(0)
			So(cmd.Execute(log), ShouldBeNil)
		})
		Convey("Revert", func() {
			So(cmd.Revert(), ShouldBeNil)
		})
		Convey("GetErrorMessage", func() {
			So(cmd.GetErrorMessage(), ShouldEqual, "failed to reboot to system")
		})
		Convey("GetStatus", func() {
			So(cmd.GetStatus(), ShouldEqual, api.InstallResponse_STATUS_PROVISIONING_FAILED)
		})
	})
}
