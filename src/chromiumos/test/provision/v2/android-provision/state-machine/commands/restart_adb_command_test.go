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

func TestRestartADBCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("RestartADBCommand", t, func() {
		associatedHost := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
		svc, _ := service.NewAndroidServiceFromExistingConnection(
			associatedHost,
			"dutSerialNumber",
			[]*api.CIPDPackage{{}},
		)
		provisionDir, _ := os.MkdirTemp("", "testCleanup")
		defer os.RemoveAll(provisionDir)

		cmd := NewRestartADBCommand(context.Background(), svc)

		Convey("Execute", func() {
			log, _ := common.SetUpLog(provisionDir)
			gomock.InOrder(
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("adb"), gomock.Eq([]string{"kill-server"})).Return("", nil).Times(1),
				associatedHost.EXPECT().CreateDirectories(gomock.Any(), gomock.Eq([]string{"/run/arc/adb"})).Return(nil).Times(1),
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("ADB_VENDOR_KEYS=/var/lib/android_keys adb"), gomock.Eq([]string{"start-server"})).Return("", nil),
			)
			So(cmd.Execute(log), ShouldBeNil)
		})
		Convey("Revert", func() {
			So(cmd.Revert(), ShouldBeNil)
		})
		Convey("GetErrorMessage", func() {
			So(cmd.GetErrorMessage(), ShouldEqual, "failed to restart ADB service")
		})
	})
}
