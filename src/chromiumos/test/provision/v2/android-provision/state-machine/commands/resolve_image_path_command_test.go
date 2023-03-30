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

func TestResolveImagePathCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("ResolveImagePathCommand", t, func() {
		associatedHost := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
		pkgProto := &api.CIPDPackage{
			AndroidPackage: api.AndroidPackage_GMS_CORE,
		}
		svc, _ := service.NewAndroidServiceFromExistingConnection(
			associatedHost,
			"dutSerialNumber",
			&api.AndroidOsImage{LocationOneof: &api.AndroidOsImage_OsVersion{OsVersion: "12"}},
			[]*api.CIPDPackage{pkgProto},
		)
		provisionDir, _ := os.MkdirTemp("", "testCleanup")
		defer os.RemoveAll(provisionDir)

		cmd := NewResolveImagePathCommand(context.Background(), svc)

		Convey("Execute", func() {
			svc.DUT.Board = "barbet"
			log, _ := common.SetUpLog(provisionDir)
			expectedGSPath := "gs://android-provisioning-images/SQ3A.220705.003.A1/barbet/"
			So(cmd.Execute(log), ShouldBeNil)
			So(svc.OS.ImagePath.GsPath, ShouldEqual, expectedGSPath)
		})
		Convey("Execute - missing board build", func() {
			svc.DUT.Board = "next_board"
			log, _ := common.SetUpLog(provisionDir)
			So(cmd.Execute(log), ShouldNotBeNil)
		})
		Convey("Revert", func() {
			So(cmd.Revert(), ShouldBeNil)
		})
		Convey("GetErrorMessage", func() {
			So(cmd.GetErrorMessage(), ShouldEqual, "failed to resolve GS image path")
		})
		Convey("GetStatus", func() {
			So(cmd.GetStatus(), ShouldEqual, api.InstallResponse_STATUS_PRE_PROVISION_SETUP_FAILED)
		})
	})
}
