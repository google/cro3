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

func TestInstallAPKCommand(t *testing.T) {
	t.Parallel()
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	Convey("InstallAPKCommand", t, func() {
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
		provisionPkg.APKFile = &service.APKFile{
			Name:          "apkName.apk",
			GsPath:        "gs_path",
			ProvisionPath: "/tmp/instanceId/apkName.apk",
		}
		provisionPkg.AndroidPackage = &service.AndroidPackage{
			PackageName: common.GMSCorePackageName,
			VersionCode: "224312037",
		}
		provisionDir, _ := os.MkdirTemp("", "testCleanup")
		defer os.RemoveAll(provisionDir)

		cmd := NewInstallAPKCommand(context.Background(), svc)

		Convey("Execute", func() {
			log, _ := common.SetUpLog(provisionDir)
			installArgs := []string{"-s", "dutSerialNumber", "install", "-r", "-d", "-g", "/tmp/instanceId/apkName.apk"}
			versionArgs := []string{"-s", "dutSerialNumber", "shell", "dumpsys", "package", common.GMSCorePackageName, "|", "grep", "versionCode", "|", "sort", "-r", "|", "head", "-n", "1"}
			gomock.InOrder(
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("adb"), gomock.Eq(installArgs)).Return("", nil).Times(1),
				associatedHost.EXPECT().RunCmd(gomock.Any(), gomock.Eq("adb"), gomock.Eq(versionArgs)).Return("versionCode=9876543210 minSdk=30 targetSdk=33", nil),
			)
			So(cmd.Execute(log), ShouldBeNil)
			So(provisionPkg.AndroidPackage.UpdatedVersionCode, ShouldResemble, "9876543210")
		})
		Convey("Revert", func() {
			So(cmd.Revert(), ShouldBeNil)
		})
		Convey("GetErrorMessage", func() {
			So(cmd.GetErrorMessage(), ShouldEqual, "failed to install APK")
		})
	})
}
