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
	luci_cipd "go.chromium.org/luci/cipd/client/cipd"
	luci_cipd_common "go.chromium.org/luci/cipd/common"

	. "github.com/smartystreets/goconvey/convey"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/common/cipd"
	"chromiumos/test/provision/v2/android-provision/service"
	mock_common_utils "chromiumos/test/provision/v2/mock-common-utils"
)

func TestResolveCIPDPackageCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("ResolveCIPDPackageCommand", t, func() {
		pkgProto := &api.CIPDPackage{
			VersionOneof: &api.CIPDPackage_InstanceId{
				InstanceId: "instanceId",
			},
			AndroidPackage: api.AndroidPackage_GMS_CORE,
		}
		associatedHost := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
		svc, _ := service.NewAndroidServiceFromExistingConnection(
			associatedHost,
			"dutSerialNumber",
			nil,
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
				provisionPkg.CIPDPackage.PackageProto.Name = "cipd_path/cipd_package_name"
				pin := luci_cipd_common.Pin{PackageName: "resolved_cipd_package_name", InstanceID: "resolvedInstanceId"}
				tags := []luci_cipd.TagInfo{{Tag: "arch:arm64"}, {Tag: "build_type:prodrvc"}, {Tag: "dpi:alldpi"}, {Tag: "version_code:222615037"}}
				d := &luci_cipd.InstanceDescription{InstanceInfo: luci_cipd.InstanceInfo{Pin: pin}, Tags: tags}
				mockCIPDClient.EXPECT().Describe(gomock.Eq(pkgProto), gomock.Eq(true), gomock.Eq(false)).Return(d, nil).Times(1)
				So(cmd.Execute(log), ShouldBeNil)
				So(provisionPkg.CIPDPackage.PackageProto.Name, ShouldEqual, "cipd_path/cipd_package_name")
				So(provisionPkg.CIPDPackage.PackageName, ShouldEqual, "resolved_cipd_package_name")
				So(provisionPkg.CIPDPackage.InstanceId, ShouldEqual, "resolvedInstanceId")
				So(provisionPkg.CIPDPackage.VersionCode, ShouldEqual, "222615037")
			})
			Convey("Resolve CIPD package name", func() {
				provisionPkg.CIPDPackage.PackageProto.Name = ""
				pin := luci_cipd_common.Pin{PackageName: "resolved_cipd_package_name", InstanceID: "resolvedInstanceId"}
				tags := []luci_cipd.TagInfo{{Tag: "arch:arm64"}, {Tag: "build_type:prodrvc"}, {Tag: "dpi:alldpi"}, {Tag: "version_code:222615037"}}
				d := &luci_cipd.InstanceDescription{InstanceInfo: luci_cipd.InstanceInfo{Pin: pin}, Tags: tags}
				versionArgs := []string{"-s", "dutSerialNumber", "shell", "getprop", "ro.build.version.release"}
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("adb"), versionArgs).Return("12", nil).Times(1)
				mockCIPDClient.EXPECT().Describe(gomock.Eq(pkgProto), gomock.Eq(true), gomock.Eq(false)).Return(d, nil).Times(1)
				So(cmd.Execute(log), ShouldBeNil)
				So(provisionPkg.CIPDPackage.PackageProto.Name, ShouldEqual, "chromiumos/infra/skylab/third_party/gmscore/gmscore_prodsc_arm64_alldpi_release_apk")
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
		Convey("GetStatus", func() {
			So(cmd.GetStatus(), ShouldEqual, api.InstallResponse_STATUS_CIPD_PACKAGE_LOOKUP_FAILED)
		})
	})
}
