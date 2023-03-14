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

func TestCopyAPKCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("CopyAPKCommand", t, func() {
		associatedHost := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
		pkgProto := &api.CIPDPackage{
			Name: "cipd_path/cipd_package_name",
			VersionOneof: &api.CIPDPackage_InstanceId{
				InstanceId: "instanceId",
			},
			AndroidPackage: api.AndroidPackage_GMS_CORE,
		}
		apkFile := &service.PkgFile{
			Name:   "apkName.apk",
			GsPath: "gsPath",
		}
		svc, _ := service.NewAndroidServiceFromExistingConnection(
			associatedHost,
			"dutSerialNumber",
			nil,
			[]*api.CIPDPackage{pkgProto},
		)
		provisionPkg := svc.ProvisionPackages[0]
		provisionPkg.CIPDPackage.InstanceId = "instanceId"
		provisionPkg.CIPDPackage.VersionCode = "versionCode"
		provisionPkg.APKFile = apkFile
		provisionDir, _ := os.MkdirTemp("", "testCleanup")
		defer os.RemoveAll(provisionDir)

		cmd := NewCopyAPKCommand(context.Background(), svc)

		Convey("Execute", func() {
			log, _ := common.SetUpLog(provisionDir)
			gomock.InOrder(
				associatedHost.EXPECT().CreateDirectories(gomock.Any(), gomock.Eq([]string{"/tmp/instanceId"})).Times(1),
				associatedHost.EXPECT().CopyData(gomock.Any(), "gsPath", "/tmp/instanceId/apkName.apk").Times(1),
			)
			So(provisionPkg.APKFile.DutPath, ShouldBeEmpty)
			So(cmd.Execute(log), ShouldBeNil)
			So(provisionPkg.APKFile.DutPath, ShouldEqual, "/tmp/instanceId/apkName.apk")
		})
		Convey("Revert", func() {
			So(cmd.Revert(), ShouldBeNil)
		})
		Convey("GetErrorMessage", func() {
			So(cmd.GetErrorMessage(), ShouldEqual, "failed to copy APK file")
		})
		Convey("GetStatus", func() {
			So(cmd.GetStatus(), ShouldEqual, api.InstallResponse_STATUS_GS_DOWNLOAD_FAILED)
		})
	})
}
