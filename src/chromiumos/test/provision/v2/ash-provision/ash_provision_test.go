// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"chromiumos/test/provision/v2/ash-provision/service"
	state_machine "chromiumos/test/provision/v2/ash-provision/state-machine"
	mock_common_utils "chromiumos/test/provision/v2/mock-common-utils"
	"context"
	"errors"
	"testing"

	"github.com/golang/mock/gomock"
	conf "go.chromium.org/chromiumos/config/go"
)

type PathExistsCommandStructure struct {
	Path string
}

type RunCommandStructure struct {
	Command string
	Args    []string
}

type CopyCommandStructure struct {
	Source string
	Dest   string
}

type PipeCommandStructure struct {
	Source  string
	Command string
}

type CreateDirsStructure struct {
	Dirs []string
}

type DeleteDirStructure struct {
	Dir string
}

// GENRAL COMMANDS
var (
	cleanUpDir                 = DeleteDirStructure{Dir: "/tmp/_provisioning_service_chrome_deploy"}
	createStagingDir           = CreateDirsStructure{Dirs: []string{"/tmp/_provisioning_service_chrome_deploy"}}
	copyImage                  = PipeCommandStructure{Source: "path/to/image", Command: "tar --ignore-command-error --overwrite --preserve-permissions --directory=/tmp/_provisioning_service_chrome_deploy -xf -"}
	createBinDirs              = CreateDirsStructure{Dirs: []string{"/opt/google/chrome", "/usr/local/autotest/deps/chrome_test/test_src/out/Release/", "/usr/local/libexec/chrome-binary-tests/"}}
	stopUI                     = RunCommandStructure{Command: "stop", Args: []string{"ui"}}
	lsofChrome                 = RunCommandStructure{Command: "lsof", Args: []string{"/opt/google/chrome/chrome"}}
	pkillChrome                = RunCommandStructure{Command: "pkill", Args: []string{"'chrome|session_manager'"}}
	mountRoot                  = RunCommandStructure{Command: "mount", Args: []string{"-o", "remount,rw", "/"}}
	checkAShShellExists        = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/ash_shell"}
	checkAuraDemoExists        = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/aura_demo"}
	checkChromeExists          = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/chrome"}
	checkChromeWrapperExists   = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/chrome-wrapper"}
	checkChromePakExists       = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/chrome.pak"}
	checkChrome100Exists       = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/chrome_100_percent.pak"}
	checkChrome200Exists       = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/chrome_200_percent.pak"}
	checkContentShellExists    = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/content_shell"}
	checkContentShellPakExists = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/content_shell.pak"}
	checkExtensionsExists      = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/extensions/"}
	checkStarSOExists          = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/lib/*.so"}
	checkLibFFExists           = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/libffmpegsumo.so"}
	checkLibPDFExists          = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/libpdf.so"}
	checkLibPPExists           = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/libppGoogleNaClPluginChrome.so"}
	checkLibOSExists           = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/libosmesa.so"}
	checkLibWideAdapterExists  = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/libwidevinecdmadapter.so"}
	checkLibWideExists         = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/libwidevinecdm.so"}
	checkLocalesExists         = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/locales/"}
	checkNaclBootstrapExists   = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/nacl_helper_bootstrap"}
	checkNaclIrtExists         = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/nacl_irt_*.nexe"}
	checkNaclHelperExists      = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/nacl_helper"}
	checkResourcesExists       = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/resources/"}
	checkResourcesPakExists    = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/resources.pak"}
	checkXDGExists             = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/xdg-settings"}
	checkStarPNGExists         = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/*.png"}
	checkStarTestExists        = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/*test"}
	checkStarTestsExists       = PathExistsCommandStructure{Path: "/tmp/_provisioning_service_chrome_deploy/*tests"}
	rsyncAuraShell             = RunCommandStructure{Command: "rsync", Args: []string{"-av", "/tmp/_provisioning_service_chrome_deploy/ash_shell", "/opt/google/chrome"}}
	rsyncExtensions            = RunCommandStructure{Command: "rsync", Args: []string{"-av", "/tmp/_provisioning_service_chrome_deploy/extensions/", "/opt/google/chrome/extensions"}}
	rsyncTestRelease           = RunCommandStructure{Command: "rsync", Args: []string{"-av", "/tmp/_provisioning_service_chrome_deploy/*test", "/usr/local/autotest/deps/chrome_test/test_src/out/Release"}}
	rsyncTestBin               = RunCommandStructure{Command: "rsync", Args: []string{"-av", "/tmp/_provisioning_service_chrome_deploy/*test", "/usr/local/libexec/chrome-binary-tests"}}
	killAll                    = RunCommandStructure{Command: "killall", Args: []string{"-HUP", "dbus-daemon"}}
	startUi                    = RunCommandStructure{Command: "start", Args: []string{"ui"}}
	deleteStagingDir           = DeleteDirStructure{Dir: "/tmp/_provisioning_service_chrome_deploy"}
)

func TestStateTransitions(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	ls := service.NewAShServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		nil)

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewAShInitState(&ls)

	gomock.InOrder(
		getDeleteDirCommand(sam, cleanUpDir).Return(nil),
		getCreateDirCommand(sam, createStagingDir).Return(nil),
		getPipeDataCommand(sam, copyImage).Return(nil),
		getCreateDirCommand(sam, createBinDirs).Return(nil),
		getRunCmdCommand(sam, stopUI).Return("", nil),
		getRunCmdCommand(sam, lsofChrome).Return("", errors.New("chrome is in use")),
		getRunCmdCommand(sam, pkillChrome).Return("", nil),
		// Make first kill soft fail so we test retry:
		getRunCmdCommand(sam, lsofChrome).Return("", errors.New("chrome is in use")),
		getRunCmdCommand(sam, pkillChrome).Return("", nil),
		// Now we let it progress
		getRunCmdCommand(sam, lsofChrome).Return("", nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed init state: %v", err)
	}
	// INSTALL
	st = st.Next()

	gomock.InOrder(
		getRunCmdCommand(sam, mountRoot).Return("", nil),
		getPathExistsCommand(sam, checkAShShellExists).Return(true, nil),
		getRunCmdCommand(sam, rsyncAuraShell).Return("", nil),
		// For all items after we make them exist so we don't need to double every item (we assume that the test isn't breakable here):
		getPathExistsCommand(sam, checkAuraDemoExists).Return(false, nil),
		getPathExistsCommand(sam, checkChromeExists).Return(false, nil),
		getPathExistsCommand(sam, checkChromeWrapperExists).Return(false, nil),
		getPathExistsCommand(sam, checkChromePakExists).Return(false, nil),
		getPathExistsCommand(sam, checkChrome100Exists).Return(false, nil),
		getPathExistsCommand(sam, checkChrome200Exists).Return(false, nil),
		getPathExistsCommand(sam, checkContentShellExists).Return(false, nil),
		getPathExistsCommand(sam, checkContentShellPakExists).Return(false, nil),
		// Testing this one specifically as it should map to the designated folder rather than the top-most:
		getPathExistsCommand(sam, checkExtensionsExists).Return(true, nil),
		getRunCmdCommand(sam, rsyncExtensions).Return("", nil),
		getPathExistsCommand(sam, checkStarSOExists).Return(false, nil),
		getPathExistsCommand(sam, checkLibFFExists).Return(false, nil),
		getPathExistsCommand(sam, checkLibPDFExists).Return(false, nil),
		getPathExistsCommand(sam, checkLibPPExists).Return(false, nil),
		getPathExistsCommand(sam, checkLibOSExists).Return(false, nil),
		getPathExistsCommand(sam, checkLibWideAdapterExists).Return(false, nil),
		getPathExistsCommand(sam, checkLibWideExists).Return(false, nil),
		getPathExistsCommand(sam, checkLocalesExists).Return(false, nil),
		getPathExistsCommand(sam, checkNaclBootstrapExists).Return(false, nil),
		getPathExistsCommand(sam, checkNaclIrtExists).Return(false, nil),
		getPathExistsCommand(sam, checkNaclHelperExists).Return(false, nil),
		getPathExistsCommand(sam, checkResourcesExists).Return(false, nil),
		getPathExistsCommand(sam, checkResourcesPakExists).Return(false, nil),
		getPathExistsCommand(sam, checkXDGExists).Return(false, nil),
		getPathExistsCommand(sam, checkStarPNGExists).Return(false, nil),

		getPathExistsCommand(sam, checkStarTestExists).Return(true, nil),
		getRunCmdCommand(sam, rsyncTestRelease).Return("", nil),
		getPathExistsCommand(sam, checkStarTestExists).Return(true, nil),
		getRunCmdCommand(sam, rsyncTestBin).Return("", nil),
		getPathExistsCommand(sam, checkStarTestsExists).Return(false, nil),
		getPathExistsCommand(sam, checkStarTestsExists).Return(false, nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed install state: %v", err)
	}

	// POST INSTALL
	st = st.Next()

	gomock.InOrder(
		getRunCmdCommand(sam, killAll).Return("", nil),
		getRunCmdCommand(sam, startUi).Return("", nil),
		getDeleteDirCommand(sam, deleteStagingDir).Return(nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed post-install state: %v", err)
	}

	// Check state completion
	if st.Next() != nil {
		t.Fatalf("post-install should be the last step")
	}
}

func TestPkillRunsOnlyForTenSeconds(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	ls := service.NewAShServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		nil)

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewAShInitState(&ls)

	gomock.InOrder(
		getDeleteDirCommand(sam, cleanUpDir).Return(nil),
		getCreateDirCommand(sam, createStagingDir).Return(nil),
		getPipeDataCommand(sam, copyImage).Return(nil),
		getCreateDirCommand(sam, createBinDirs).Return(nil),
		getRunCmdCommand(sam, stopUI).Return("", nil),
	)

	getRunCmdCommand(sam, lsofChrome).Return("", errors.New("chrome is in use!")).AnyTimes()
	getRunCmdCommand(sam, pkillChrome).Return("", nil).AnyTimes()

	if err := st.Execute(ctx); err == nil {
		t.Fatalf("init state should have failed!")
	}
}

func getPathExistsCommand(sam *mock_common_utils.MockServiceAdapterInterface, s PathExistsCommandStructure) *gomock.Call {
	return sam.EXPECT().PathExists(gomock.Any(), gomock.Eq(s.Path))
}

func getCreateDirCommand(sam *mock_common_utils.MockServiceAdapterInterface, s CreateDirsStructure) *gomock.Call {
	return sam.EXPECT().CreateDirectories(gomock.Any(), gomock.Eq(s.Dirs))
}

func getDeleteDirCommand(sam *mock_common_utils.MockServiceAdapterInterface, s DeleteDirStructure) *gomock.Call {
	return sam.EXPECT().DeleteDirectory(gomock.Any(), gomock.Eq(s.Dir))
}

func getCopyDataCommand(sam *mock_common_utils.MockServiceAdapterInterface, s CopyCommandStructure) *gomock.Call {
	return sam.EXPECT().CopyData(gomock.Any(), gomock.Eq(s.Source), gomock.Eq(s.Dest))
}

func getPipeDataCommand(sam *mock_common_utils.MockServiceAdapterInterface, s PipeCommandStructure) *gomock.Call {
	return sam.EXPECT().PipeData(gomock.Any(), gomock.Eq(s.Source), gomock.Eq(s.Command))
}

func getRunCmdCommand(sam *mock_common_utils.MockServiceAdapterInterface, s RunCommandStructure) *gomock.Call {
	return sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq(s.Command), gomock.Eq(s.Args))
}
