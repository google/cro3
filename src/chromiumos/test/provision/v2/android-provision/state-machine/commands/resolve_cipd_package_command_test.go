// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"os"
	"testing"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/common/cipd"
	"github.com/golang/mock/gomock"
	"go.chromium.org/chromiumos/config/go/test/api"
	luci_cipd "go.chromium.org/luci/cipd/client/cipd"
	luci_cipd_common "go.chromium.org/luci/cipd/common"

	. "github.com/smartystreets/goconvey/convey"

	"chromiumos/test/provision/v2/android-provision/service"
)

func TestResolveCIPDPackageCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("ResolveCIPDPackageCommand", t, func() {
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
		provisionPkg := svc.ProvisionPackages[0]
		provisionDir, _ := os.MkdirTemp("", "testCleanup")
		defer os.RemoveAll(provisionDir)

		cmd := NewResolveCIPDPackageCommand(context.Background(), svc)

		Convey("Execute", func() {
			log, _ := common.SetUpLog(provisionDir)
			mockCIPDClient := cipd.NewMockCIPDClientInterface(ctrl)
			cmd.cipd = mockCIPDClient
			Convey("New Android Package", func() {
				pin := luci_cipd_common.Pin{PackageName: "resolved_cipd_package_name", InstanceID: "resolvedInstanceId"}
				tags := []luci_cipd.TagInfo{{Tag: "arch:arm64"}, {Tag: "build_type:prodrvc"}, {Tag: "dpi:alldpi"}, {Tag: "version_code:222615037"}}
				d := &luci_cipd.InstanceDescription{InstanceInfo: luci_cipd.InstanceInfo{Pin: pin}, Tags: tags}
				mockCIPDClient.EXPECT().Describe(gomock.Eq(pkgProto), gomock.Eq(true), gomock.Eq(false)).Return(d, nil).Times(1)
				So(cmd.Execute(log), ShouldBeNil)
				So(provisionPkg.CIPDPackage.PackageName, ShouldEqual, "resolved_cipd_package_name")
				So(provisionPkg.CIPDPackage.InstanceId, ShouldEqual, "resolvedInstanceId")
				So(provisionPkg.CIPDPackage.VersionCode, ShouldEqual, "222615037")
			})
		})
		Convey("Revert", func() {
			So(cmd.Revert(), ShouldBeNil)
		})
		Convey("GetErrorMessage", func() {
			So(cmd.GetErrorMessage(), ShouldEqual, "failed to resolve CIPD package")
		})
	})
}
