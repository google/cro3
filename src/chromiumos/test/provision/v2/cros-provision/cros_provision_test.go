// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/cli"
	"chromiumos/test/provision/v2/cros-provision/constants"
	"chromiumos/test/provision/v2/cros-provision/service"
	state_machine "chromiumos/test/provision/v2/cros-provision/state-machine"
	mock_common_utils "chromiumos/test/provision/v2/mock-common-utils"
	"context"
	"fmt"
	"testing"

	"github.com/golang/mock/gomock"
	conf "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
)

const (
	mockedValidCrosidStdout           = "SKU=33\nCONFIG_INDEX=9\nFIRMWARE_MANIFEST_KEY='babytiger'\n"
	mockedValidFirmwareManifestStdout = "{\n  \"babytiger\": {\n    \"host\": { \"versions\": { \"ro\": \"Google_Coral.10068.113.0\", \"rw\": \"Google_Coral.10068.113.0\" },\n      \"keys\": { \"root\": \"b11d74edd286c144e1135b49e7f0bc20cf041f10\", \"recovery\": \"c14bd720b70d97394257e3e826bd8f43de48d4ed\" },\n      \"image\": \"images/bios-coral.ro-10068-113-0.rw-10068-113-0.bin\" },\n    \"ec\": { \"versions\": { \"ro\": \"coral_v1.1.7302-d2b56e247\", \"rw\": \"coral_v1.1.7302-d2b56e247\" },\n      \"image\": \"images/ec-coral.ro-1-1-7302.rw-1-1-7302.bin\" },\n    \"signature_id\": \"babytiger\"\n  }\n}\n"
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
	createProvisionMarker     = RunCommandStructure{Command: "touch", Args: []string{"/var/tmp/provision_failed"}}
	rootDevPartition          = RunCommandStructure{Command: "rootdev", Args: []string{"-s"}}
	rootDevDisk               = RunCommandStructure{Command: "rootdev", Args: []string{"-s", "-d"}}
	getBoard                  = RunCommandStructure{Command: "cat", Args: []string{"/etc/lsb-release"}}
	stopUI                    = RunCommandStructure{Command: "stop", Args: []string{"ui"}}
	stopUpdateEngine          = RunCommandStructure{Command: "stop", Args: []string{"update-engine"}}
	dlcLibExists              = PathExistsCommandStructure{Path: common_utils.DlcLibDir}
	stopDLCservice            = RunCommandStructure{Command: "stop", Args: []string{"dlcservice"}}
	removeVerified            = RunCommandStructure{Command: "rm", Args: []string{"-f", "/var/cache/dlc/*/*/dlc_b/verified"}}
	startDLCservice           = RunCommandStructure{Command: "start", Args: []string{"dlcservice"}}
	copyKernel                = PipeCommandStructure{Source: "gs://path/to/image/full_dev_part_KERN.bin.gz", Command: "gzip -d | dd of=root_diskroot4 obs=2M \npipestatus=(\"${PIPESTATUS[@]}\")\nif [[ \"${pipestatus[0]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Fetching path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[1]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Decompressing path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[2]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Writing to root_diskroot4 failed.\" >&2\n  exit 1\nfi"}
	copyRoot                  = PipeCommandStructure{Source: "gs://path/to/image/full_dev_part_ROOT.bin.gz", Command: "gzip -d | dd of=root_diskroot5 obs=2M \npipestatus=(\"${PIPESTATUS[@]}\")\nif [[ \"${pipestatus[0]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Fetching path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[1]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Decompressing path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[2]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Writing to root_diskroot5 failed.\" >&2\n  exit 1\nfi"}
	makeTemp                  = RunCommandStructure{Command: "mktemp", Args: []string{"-d"}}
	mountTemp                 = RunCommandStructure{Command: "mount", Args: []string{"-o", "ro", "root_diskroot5", "temporary_dir"}}
	postInstTemp              = RunCommandStructure{Command: "temporary_dir/postinst", Args: []string{"root_diskroot5"}}
	umountTemp                = RunCommandStructure{Command: "umount", Args: []string{"temporary_dir"}}
	deleteTemp                = RunCommandStructure{Command: "rmdir", Args: []string{"temporary_dir"}}
	crosSystem                = RunCommandStructure{Command: "crossystem", Args: []string{"clear_tpm_owner_request=1"}}
	waitforStabilize          = RunCommandStructure{Command: "status", Args: []string{"system-services"}}
	echoFastKeepImg           = RunCommandStructure{Command: "echo", Args: []string{"'fast keepimg'", ">", "/mnt/stateful_partition/factory_install_reset"}}
	cleanPostInstall          = RunCommandStructure{Command: "rm", Args: []string{"-rf", "/mnt/stateful_partition/.update_available", "/mnt/stateful_partition/var_new", "/mnt/stateful_partition/dev_image_new"}}
	copyStateful              = PipeCommandStructure{Source: "gs://path/to/image/stateful.tgz", Command: "tar --ignore-command-error --overwrite --directory=/mnt/stateful_partition --selinux -xzf -"}
	createUpdateAvailableFile = RunCommandStructure{Command: "echo", Args: []string{"-n", "clobber", ">", "/mnt/stateful_partition/.update_available"}}
	dlcAVerifiedExists        = PathExistsCommandStructure{Path: "/var/lib/dlcservice/dlc/1/dlc_a/verified"}
	createDLCDir              = CreateDirsStructure{Dirs: []string{"/var/cache/dlc/1/package/dlc_a"}}
	chownDLCs                 = RunCommandStructure{Command: "chown", Args: []string{"-R", "dlcservice:dlcservice", "/var/cache/dlc"}}
	chmodDLCs                 = RunCommandStructure{Command: "chmod", Args: []string{"-R", "0755", "/var/cache/dlc"}}
	cgptRoot9                 = RunCommandStructure{Command: "cgpt", Args: []string{"show", "-t", "root_disk", "-i", "9"}}
	cgptRoot10                = RunCommandStructure{Command: "cgpt", Args: []string{"show", "-t", "root_disk", "-i", "10"}}
	copyMiniOS9               = PipeCommandStructure{Source: "gs://path/to/image/full_dev_part_MINIOS.bin.gz", Command: "gzip -d | dd of=root_diskroot9 obs=2M \npipestatus=(\"${PIPESTATUS[@]}\")\nif [[ \"${pipestatus[0]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Fetching path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[1]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Decompressing path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[2]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Writing to root_diskroot9 failed.\" >&2\n  exit 1\nfi"}
	copyMiniOS10              = PipeCommandStructure{Source: "gs://path/to/image/full_dev_part_MINIOS.bin.gz", Command: "gzip -d | dd of=root_diskroot10 obs=2M \npipestatus=(\"${PIPESTATUS[@]}\")\nif [[ \"${pipestatus[0]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Fetching path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[1]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Decompressing path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[2]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Writing to root_diskroot10 failed.\" >&2\n  exit 1\nfi"}
	checkFirmwareUpdater      = PathExistsCommandStructure{Path: common_utils.FirmwareUpdaterPath}
	updateFirmware            = RunCommandStructure{Command: common_utils.FirmwareUpdaterPath, Args: []string{"--wp=1", "--mode=autoupdate"}}
	currentFirmwareSlot       = RunCommandStructure{Command: "crossystem", Args: []string{common_utils.CrossystemCurrentFirmwareSlotKey}}
	nextFirmwareSlot          = RunCommandStructure{Command: "crossystem", Args: []string{common_utils.CrossystemNextFirmwareSlotKey}}
	firmwareManifest          = RunCommandStructure{Command: common_utils.FirmwareUpdaterPath, Args: []string{"--manifest"}}
	getCrosid                 = RunCommandStructure{Command: "crosid", Args: []string{}}
	getCurrentFirmware        = RunCommandStructure{Command: "crossystem", Args: []string{"fwid"}}
)

// REVERT COMMANDS
var (
	cleanPostInstallRevert = RunCommandStructure{Command: "rm", Args: []string{"-rf", "/mnt/stateful_partition/var_new", "/mnt/stateful_partition/dev_image_new", "/mnt/stateful_partition/.update_available"}}
	postInstRevert         = RunCommandStructure{Command: "/postinst", Args: []string{"root_diskroot3", "2>&1"}}
)

// OVERWRITE COMMANDS
var (
	copyOverwritePayload = PipeCommandStructure{Source: "path/to/image/overwite.tar", Command: "tar xf - -C /"}
)

func TestStateTransitions(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	log, _ := cli.SetUpLog(constants.DefaultLogDirectory)
	cs := service.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		nil,
		false,
		[]*api.CrOSProvisionMetadata_DLCSpec{{Id: "1"}},
		true, // FirmwareUpdate enabled.
	)

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewCrOSInitState(&cs)

	gomock.InOrder(
		getRunCmdCommand(sam, createProvisionMarker).Return("", nil),
		getRunCmdCommand(sam, rootDevPartition).Return(fmt.Sprintf("root%s", common_utils.PartitionNumRootA), nil),
		getRunCmdCommand(sam, rootDevDisk).Return("root_disk", nil),
		getRunCmdCommand(sam, getBoard).Return("CHROMEOS_RELEASE_BOARD=(not_reven)", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed init state: %v", err)
	}

	// INSTALL
	st = st.Next()

	gomock.InOrder(
		getRunCmdCommand(sam, stopUI).Return("", nil),
		getRunCmdCommand(sam, stopUpdateEngine).Return("", nil),
		getPathExistsCommand(sam, dlcLibExists).Return(true, nil),
		getRunCmdCommand(sam, stopDLCservice).Return("", nil),
		getRunCmdCommand(sam, removeVerified).Return("", nil),
		getRunCmdCommand(sam, startDLCservice).Return("", nil),
		getPipeDataCommand(sam, copyKernel).Return(nil),
		getPipeDataCommand(sam, copyRoot).Return(nil),
		getRunCmdCommand(sam, makeTemp).Return("temporary_dir", nil),
		getRunCmdCommand(sam, mountTemp).Return("", nil),
		getRunCmdCommand(sam, postInstTemp).Return("", nil),
		getRunCmdCommand(sam, umountTemp).Return("", nil),
		getRunCmdCommand(sam, deleteTemp).Return("", nil),
		getRunCmdCommand(sam, crosSystem).Return("", nil),
		getRestartCommand(sam).Return(nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed install state: %v", err)
	}

	// UPDATE FIRMWARE
	st = st.Next()

	gomock.InOrder(
		getPathExistsCommand(sam, checkFirmwareUpdater).Return(true, nil),
		getRunCmdCommand(sam, waitforStabilize).Return("start/running", nil),
		getRunCmdCommand(sam, updateFirmware).Return("", nil),
		getRunCmdCommand(sam, currentFirmwareSlot).Return("A", nil),
		getRunCmdCommand(sam, nextFirmwareSlot).Return("B", nil),
		getRestartCommand(sam).Return(nil),
		getRunCmdCommand(sam, firmwareManifest).Return(mockedValidFirmwareManifestStdout, nil),
		getRunCmdCommand(sam, getCrosid).Return(mockedValidCrosidStdout, nil),
		getRunCmdCommand(sam, getCurrentFirmware).Return("Google_Coral.10068.113.0", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed firmware-update state: %v", err)
	}

	// POST INSTALL
	st = st.Next()

	gomock.InOrder(
		getRunCmdCommand(sam, waitforStabilize).Return("start/running", nil),
		getRunCmdCommand(sam, echoFastKeepImg).Return("", nil),
		getRestartCommand(sam).Return(nil),
		getRunCmdCommand(sam, stopUI).Return("", nil),
		getRunCmdCommand(sam, stopUpdateEngine).Return("", nil),
		getRunCmdCommand(sam, cleanPostInstall).Return("", nil),
		getPipeDataCommand(sam, copyStateful).Return(nil),
		getRunCmdCommand(sam, createUpdateAvailableFile).Return("", nil),
		getRestartCommand(sam).Return(nil),
		getRunCmdCommand(sam, rootDevPartition).Return(fmt.Sprintf("root%s", common_utils.PartitionNumRootA), nil),
		getRunCmdCommand(sam, rootDevDisk).Return("root_disk", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed post-install state: %v", err)
	}

	// VERIFY
	st = st.Next()

	gomock.InOrder()

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed verify state: %v", err)
	}

	// INSTALL DLCS
	st = st.Next()

	gomock.InOrder(
		getRunCmdCommand(sam, stopDLCservice).Return("", nil),
	)
	// Concurrent Portion
	// Return not verfied so we can test full case:
	getPathExistsCommand(sam, dlcAVerifiedExists).Return(false, nil)
	getCreateDirCommand(sam, createDLCDir).Return(nil)
	sam.EXPECT().CopyData(gomock.Any(), gomock.Any(), gomock.Eq("/var/cache/dlc/1/package/dlc_a/dlc.img")).Return(nil)
	getRunCmdCommand(sam, startDLCservice).Times(1).Return("", nil)

	gomock.InOrder(
		getRunCmdCommand(sam, chownDLCs).Return("", nil),
		getRunCmdCommand(sam, chmodDLCs).Return("", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed install DLCs state: %v", err)
	}

	// INSTALL MINIOS
	st = st.Next()

	gomock.InOrder(
		getRunCmdCommand(sam, cgptRoot9).Return("09845860-705F-4BB5-B16C-8A8A099CAF52", nil),
		getRunCmdCommand(sam, cgptRoot10).Return("09845860-705F-4BB5-B16C-8A8A099CAF52", nil),
		getPipeDataCommand(sam, copyMiniOS9).Return(nil),
		getPipeDataCommand(sam, copyMiniOS10).Return(nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed install MiniOS state: %v", err)
	}

	// Check state completion
	if st.Next() != nil {
		t.Fatalf("install minios should be the last step")
	}
}

func TestInstallPostInstallFailureCausesReversal(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	log, _ := cli.SetUpLog(constants.DefaultLogDirectory)
	cs := service.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		nil,
		false,
		[]*api.CrOSProvisionMetadata_DLCSpec{{Id: "1"}},
		false,
	)

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewCrOSInitState(&cs)

	gomock.InOrder(
		getRunCmdCommand(sam, createProvisionMarker).Return("", nil),
		getRunCmdCommand(sam, rootDevPartition).Return(fmt.Sprintf("root%s", common_utils.PartitionNumRootA), nil),
		getRunCmdCommand(sam, rootDevDisk).Return("root_disk", nil),
		getRunCmdCommand(sam, getBoard).Return("CHROMEOS_RELEASE_BOARD=(not_reven)", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed init state: %v", err)
	}

	// INSTALL
	st = st.Next()

	gomock.InOrder(
		getRunCmdCommand(sam, stopUI).Return("", nil),
		getRunCmdCommand(sam, stopUpdateEngine).Return("", nil),
		getPathExistsCommand(sam, dlcLibExists).Return(true, nil),
		getRunCmdCommand(sam, stopDLCservice).Return("", nil),
		getRunCmdCommand(sam, removeVerified).Return("", nil),
		getRunCmdCommand(sam, startDLCservice).Return("", nil),
		getPipeDataCommand(sam, copyKernel).Return(nil),
		getPipeDataCommand(sam, copyRoot).Return(nil),
		getRunCmdCommand(sam, makeTemp).Return("temporary_dir", nil),
		getRunCmdCommand(sam, mountTemp).Return("", nil),
		getRunCmdCommand(sam, postInstTemp).Return("", nil),
		getRunCmdCommand(sam, umountTemp).Return("", nil),
		getRunCmdCommand(sam, deleteTemp).Return("", fmt.Errorf("postinstall error")),
		getRunCmdCommand(sam, cleanPostInstallRevert).Return("", nil),
		getRunCmdCommand(sam, postInstRevert).Return("", nil),
	)

	if _, _, err := st.Execute(ctx, log); err.Error() != "failed to post install, failed to remove temporary directory, postinstall error" {
		t.Fatalf("expected specific error, instead got: %v", err)
	}
}

func TestInstallClearTPMFailureCausesReversal(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	log, _ := cli.SetUpLog(constants.DefaultLogDirectory)
	cs := service.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		nil,
		false,
		[]*api.CrOSProvisionMetadata_DLCSpec{{Id: "1"}},
		false,
	)

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewCrOSInitState(&cs)

	gomock.InOrder(
		getRunCmdCommand(sam, createProvisionMarker).Return("", nil),
		getRunCmdCommand(sam, rootDevPartition).Return(fmt.Sprintf("root%s", common_utils.PartitionNumRootA), nil),
		getRunCmdCommand(sam, rootDevDisk).Return("root_disk", nil),
		getRunCmdCommand(sam, getBoard).Return("CHROMEOS_RELEASE_BOARD=(not_reven)", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed init state: %v", err)
	}

	// INSTALL
	st = st.Next()

	gomock.InOrder(
		getRunCmdCommand(sam, stopUI).Return("", nil),
		getRunCmdCommand(sam, stopUpdateEngine).Return("", nil),
		getPathExistsCommand(sam, dlcLibExists).Return(true, nil),
		getRunCmdCommand(sam, stopDLCservice).Return("", nil),
		getRunCmdCommand(sam, removeVerified).Return("", nil),
		getRunCmdCommand(sam, startDLCservice).Return("", nil),
		getPipeDataCommand(sam, copyKernel).Return(nil),
		getPipeDataCommand(sam, copyRoot).Return(nil),
		getRunCmdCommand(sam, makeTemp).Return("temporary_dir", nil),
		getRunCmdCommand(sam, mountTemp).Return("", nil),
		getRunCmdCommand(sam, postInstTemp).Return("", nil),
		getRunCmdCommand(sam, umountTemp).Return("", nil),
		getRunCmdCommand(sam, deleteTemp).Return("", nil),
		getRunCmdCommand(sam, crosSystem).Return("", fmt.Errorf("clear TPM error")),
		getRunCmdCommand(sam, cleanPostInstallRevert).Return("", nil),
		getRunCmdCommand(sam, postInstRevert).Return("", nil),
	)

	if _, _, err := st.Execute(ctx, log); err.Error() != "failed to clear TPM, clear TPM error" {
		t.Fatalf("expected specific error, instead got: %v", err)
	}
}

func TestFirmwareUpdateStateSkippedDueToNoUpdaterExist(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	log, _ := cli.SetUpLog(constants.DefaultLogDirectory)
	cs := service.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		nil,
		false,
		[]*api.CrOSProvisionMetadata_DLCSpec{{Id: "1"}},
		true,
	)

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewCrOSInitState(&cs)

	gomock.InOrder(
		getRunCmdCommand(sam, createProvisionMarker).Return("", nil),
		getRunCmdCommand(sam, rootDevPartition).Return(fmt.Sprintf("root%s", common_utils.PartitionNumRootA), nil),
		getRunCmdCommand(sam, rootDevDisk).Return("root_disk", nil),
		getRunCmdCommand(sam, getBoard).Return("CHROMEOS_RELEASE_BOARD=(not_reven)", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed init state: %v", err)
	}

	// -> INSTALL -> FIRMWARE-UPDATE
	st = st.Next().Next()

	gomock.InOrder(
		getPathExistsCommand(sam, checkFirmwareUpdater).Return(true, nil),
		getRunCmdCommand(sam, waitforStabilize).Return("start/running", nil),
		getRunCmdCommand(sam, updateFirmware).Return("", nil),
		getRunCmdCommand(sam, currentFirmwareSlot).Return("A", nil),
		getRunCmdCommand(sam, nextFirmwareSlot).Return("A", nil),
		getRunCmdCommand(sam, firmwareManifest).Return(mockedValidFirmwareManifestStdout, nil),
		getRunCmdCommand(sam, getCrosid).Return(mockedValidCrosidStdout, nil),
		getRunCmdCommand(sam, getCurrentFirmware).Return("Google_Coral.10068.113.0", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed firmware-update state: %v", err)
	}
}

func TestFirmwareUpdateStateWithNoChange(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	log, _ := cli.SetUpLog(constants.DefaultLogDirectory)
	cs := service.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		nil,
		false,
		[]*api.CrOSProvisionMetadata_DLCSpec{{Id: "1"}},
		true,
	)

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewCrOSInitState(&cs)

	gomock.InOrder(
		getRunCmdCommand(sam, createProvisionMarker).Return("", nil),
		getRunCmdCommand(sam, rootDevPartition).Return(fmt.Sprintf("root%s", common_utils.PartitionNumRootA), nil),
		getRunCmdCommand(sam, rootDevDisk).Return("root_disk", nil),
		getRunCmdCommand(sam, getBoard).Return("CHROMEOS_RELEASE_BOARD=(not_reven)", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed init state: %v", err)
	}

	// -> INSTALL -> FIRMWARE-UPDATE
	st = st.Next().Next()

	gomock.InOrder(
		getPathExistsCommand(sam, checkFirmwareUpdater).Return(false, nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed firmware-update state: %v", err)
	}
}

func TestPostInstallStatePreservesStatefulWhenRequested(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	log, _ := cli.SetUpLog(constants.DefaultLogDirectory)
	cs := service.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		nil,
		true, // <- preserve stateful
		[]*api.CrOSProvisionMetadata_DLCSpec{{Id: "1"}},
		false,
	)

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewCrOSInitState(&cs)

	gomock.InOrder(
		getRunCmdCommand(sam, createProvisionMarker).Return("", nil),
		getRunCmdCommand(sam, rootDevPartition).Return(fmt.Sprintf("root%s", common_utils.PartitionNumRootA), nil),
		getRunCmdCommand(sam, rootDevDisk).Return("root_disk", nil),
		getRunCmdCommand(sam, getBoard).Return("CHROMEOS_RELEASE_BOARD=(not_reven)", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed init state: %v", err)
	}

	// -> INSTALL -> FIRMWARE-UPDATE -> POST-INSTALL
	st = st.Next().Next().Next()

	gomock.InOrder(
		getRunCmdCommand(sam, waitforStabilize).Return("start/running", nil),
		// Delete steps elided due to preserve stateful
		getRunCmdCommand(sam, stopUI).Return("", nil),
		getRunCmdCommand(sam, stopUpdateEngine).Return("", nil),
		getRunCmdCommand(sam, cleanPostInstall).Return("", nil),
		getPipeDataCommand(sam, copyStateful).Return(nil),
		getRunCmdCommand(sam, createUpdateAvailableFile).Return("", nil),
		getRestartCommand(sam).Return(nil),
		getRunCmdCommand(sam, rootDevPartition).Return(fmt.Sprintf("root%s", common_utils.PartitionNumRootA), nil),
		getRunCmdCommand(sam, rootDevDisk).Return("root_disk", nil),
	)

	// Nothing should be run, so no need to use mock expect
	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed post-install state: %v", err)
	}
}

func TestPostInstallStatefulFailsGetsReversed(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	log, _ := cli.SetUpLog(constants.DefaultLogDirectory)
	cs := service.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		nil,
		true, // <- preserve stateful
		[]*api.CrOSProvisionMetadata_DLCSpec{{Id: "1"}},
		false,
	)

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewCrOSInitState(&cs)

	gomock.InOrder(
		getRunCmdCommand(sam, createProvisionMarker).Return("", nil),
		getRunCmdCommand(sam, rootDevPartition).Return(fmt.Sprintf("root%s", common_utils.PartitionNumRootA), nil),
		getRunCmdCommand(sam, rootDevDisk).Return("root_disk", nil),
		getRunCmdCommand(sam, getBoard).Return("CHROMEOS_RELEASE_BOARD=(not_reven)", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed init state: %v", err)
	}

	// -> INSTALL -> FIRMWARE-UPDATE -> POST-INSTALL
	st = st.Next().Next().Next()

	gomock.InOrder(
		getRunCmdCommand(sam, waitforStabilize).Return("start/running", nil),
		// Delete steps elided due to preserve stateful
		getRunCmdCommand(sam, stopUI).Return("", nil),
		getRunCmdCommand(sam, stopUpdateEngine).Return("", nil),
		getRunCmdCommand(sam, cleanPostInstall).Return("", nil),
		// Simulated error:
		getPipeDataCommand(sam, copyStateful).Return(fmt.Errorf("copy error")),
		getRunCmdCommand(sam, cleanPostInstallRevert).Return("", nil),
	)

	if _, _, err := st.Execute(ctx, log); err.Error() != "failed to provision stateful, copy error" {
		t.Fatalf("Post install should've failed with specific error, instead got: %v", err)
	}
}

func TestProvisionDLCWithEmptyDLCsDoesNotExecute(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	log, _ := cli.SetUpLog(constants.DefaultLogDirectory)
	cs := service.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		nil,
		false,
		[]*api.CrOSProvisionMetadata_DLCSpec{}, // <- empty
		false,
	)

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewCrOSInitState(&cs)

	gomock.InOrder(
		getRunCmdCommand(sam, createProvisionMarker).Return("", nil),
		getRunCmdCommand(sam, rootDevPartition).Return(fmt.Sprintf("root%s", common_utils.PartitionNumRootA), nil),
		getRunCmdCommand(sam, rootDevDisk).Return("root_disk", nil),
		getRunCmdCommand(sam, getBoard).Return("CHROMEOS_RELEASE_BOARD=(not_reven)", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed init state: %v", err)
	}

	// -> INSTALL -> FIRMWARE-UPDATE -> POST-INSTALL -> VERIFY -> DLC
	st = st.Next().Next().Next().Next().Next()

	// Nothing should be run, so no need to use mock expect
	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed provision-dlc state: %v", err)
	}
}

func TestProvisionDLCWhenVerifyIsTrueDoesNotExecuteInstall(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	log, _ := cli.SetUpLog(constants.DefaultLogDirectory)
	cs := service.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		nil,
		false,
		[]*api.CrOSProvisionMetadata_DLCSpec{{Id: "1"}},
		false,
	)

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewCrOSInitState(&cs)

	gomock.InOrder(
		getRunCmdCommand(sam, createProvisionMarker).Return("", nil),
		getRunCmdCommand(sam, rootDevPartition).Return(fmt.Sprintf("root%s", common_utils.PartitionNumRootA), nil),
		getRunCmdCommand(sam, rootDevDisk).Return("root_disk", nil),
		getRunCmdCommand(sam, getBoard).Return("CHROMEOS_RELEASE_BOARD=(not_reven)", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed init state: %v", err)
	}

	// -> INSTALL -> FIRMWARE-UPDATE -> POST-INSTALL -> VERIFY -> DLC
	st = st.Next().Next().Next().Next().Next()

	gomock.InOrder(
		getRunCmdCommand(sam, stopDLCservice).Return("", nil),
	)
	// Concurrent Portion
	// Return verfied so install stops here:
	getPathExistsCommand(sam, dlcAVerifiedExists).Return(true, nil)
	getRunCmdCommand(sam, startDLCservice).Times(1).Return("", nil)

	gomock.InOrder(
		getRunCmdCommand(sam, chownDLCs).Return("", nil),
		getRunCmdCommand(sam, chmodDLCs).Return("", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed provision-dlc state: %v", err)
	}
}

func TestPostInstallOverwriteWhenSpecified(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	log, _ := cli.SetUpLog(constants.DefaultLogDirectory)
	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	cs := service.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image/overwite.tar",
		},
		false,
		[]*api.CrOSProvisionMetadata_DLCSpec{{Id: "1"}},
		false,
	)

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewCrOSInitState(&cs)

	gomock.InOrder(
		getRunCmdCommand(sam, createProvisionMarker).Return("", nil),
		getRunCmdCommand(sam, rootDevPartition).Return(fmt.Sprintf("root%s", common_utils.PartitionNumRootA), nil),
		getRunCmdCommand(sam, rootDevDisk).Return("root_disk", nil),
		getRunCmdCommand(sam, getBoard).Return("CHROMEOS_RELEASE_BOARD=(not_reven)", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed init state: %v", err)
	}

	// -> INSTALL -> FIRMWARE-UPDATE -> POST-INSTALL
	st = st.Next().Next().Next()

	gomock.InOrder(
		getRunCmdCommand(sam, waitforStabilize).Return("start/running", nil),
		getRunCmdCommand(sam, echoFastKeepImg).Return("", nil),
		getRestartCommand(sam).Return(nil),
		getRunCmdCommand(sam, stopUI).Return("", nil),
		getRunCmdCommand(sam, stopUpdateEngine).Return("", nil),
		getRunCmdCommand(sam, cleanPostInstall).Return("", nil),
		getPipeDataCommand(sam, copyStateful).Return(nil),
		getRunCmdCommand(sam, createUpdateAvailableFile).Return("", nil),
		getRestartCommand(sam).Return(nil),
		getPipeDataCommand(sam, copyOverwritePayload).Return(nil),
		getRestartCommand(sam).Return(nil),
		getRunCmdCommand(sam, rootDevPartition).Return(fmt.Sprintf("root%s", common_utils.PartitionNumRootA), nil),
		getRunCmdCommand(sam, rootDevDisk).Return("root_disk", nil),
	)

	if _, _, err := st.Execute(ctx, log); err != nil {
		t.Fatalf("failed post-install state: %v", err)
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

func getRestartCommand(sam *mock_common_utils.MockServiceAdapterInterface) *gomock.Call {
	return sam.EXPECT().Restart(gomock.Any())
}
