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
	"chromiumos/test/provision/v2/android-provision/common/zip"
	"chromiumos/test/provision/v2/android-provision/service"
)

func TestExtractAPKFileCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("ExtractAPKFileCommand", t, func() {
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
		svc, _ := service.NewAndroidServiceFromExistingConnection(
			nil,
			"",
			[]*api.CIPDPackage{pkgProto},
		)
		provisionPkg := svc.ProvisionPackages[0]
		provisionPkg.CIPDPackage = cipdPkg
		provisionDir, _ := os.MkdirTemp("", "testCleanup")
		defer os.RemoveAll(provisionDir)
		svc.ProvisionDir = provisionDir

		cmd := NewExtractAPKFileCommand(context.Background(), svc)

		Convey("Execute", func() {
			log, _ := common.SetUpLog(provisionDir)
			mockZipReader := zip.NewMockZipReaderInterface(ctrl)
			cmd.zip = mockZipReader

			mockZipReader.EXPECT().UnzipFile(gomock.Eq("/tmp/instanceId/cipd_package_name.zip"), gomock.Eq(provisionDir+"/instanceId")).Times(1)
			So(cmd.Execute(log), ShouldBeNil)
		})
		Convey("Revert", func() {
			So(cmd.Revert(), ShouldBeNil)
		})
		Convey("GetErrorMessage", func() {
			So(cmd.GetErrorMessage(), ShouldEqual, "failed to extract APK file")
		})
		Convey("GetStatus", func() {
			So(cmd.GetStatus(), ShouldEqual, api.InstallResponse_STATUS_PRE_PROVISION_SETUP_FAILED)
		})
	})
}
