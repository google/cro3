// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"chromiumos/test/provision/v2/lacros-provision/service"
	state_machine "chromiumos/test/provision/v2/lacros-provision/state-machine"
	mock_common_utils "chromiumos/test/provision/v2/mock-common-utils"
	"context"
	"encoding/json"
	"testing"

	"github.com/golang/mock/gomock"
	conf "go.chromium.org/chromiumos/config/go"
)

type RunCommandStructure struct {
	Command string
	Args    []string
}

type CopyCommandStructure struct {
	Source string
	Dest   string
}

type CreateDirsStructure struct {
	Dirs []string
}

// JSON
var (
	json_data, _ = json.MarshalIndent(struct {
		ManifestVersion int    `json:"manifest-version"`
		FsType          string `json:"fs-type"`
		Version         string `json:"version"`
		ImageSha256Hash string `json:"image-sha256-hash"`
		TableSha256Hash string `json:"table-sha256-hash"`
	}{
		ManifestVersion: 1,
		FsType:          "squashfs",
		Version:         "v1",
		ImageSha256Hash: "image_hash",
		TableSha256Hash: "table_hash",
	}, "", "  ")
	component_json_data, _ = json.MarshalIndent(struct {
		ManifestVersion int    `json:"manifest-version"`
		Name            string `json:"name"`
		Version         string `json:"version"`
		ImageName       string `json:"imageName"`
		Squash          bool   `json:"squash"`
		FsType          string `json:"fsType"`
		IsRemovable     bool   `json:"isRemovable"`
	}{
		ManifestVersion: 2,
		Name:            "lacros",
		Version:         "v1",
		ImageName:       "image.squash",
		Squash:          true,
		FsType:          "squashfs",
		IsRemovable:     false,
	}, "", "  ")
)

// GENRAL COMMANDS
var (
	copyMetadataCommand     = CopyCommandStructure{Source: "path/to/image/metadata.json", Dest: "/tmp/metadata.json"}
	runMeowMetadataCommand  = RunCommandStructure{Command: "cat", Args: []string{"/tmp/metadata.json"}}
	createLaCrOSDirsCommand = CreateDirsStructure{Dirs: []string{"/var/lib/imageloader/lacros/v1"}}
	copyLaCrOSImageCommand  = CopyCommandStructure{Source: "path/to/image/lacros_compressed.squash", Dest: "/var/lib/imageloader/lacros/v1/image.squash"}
	runStatCommand          = RunCommandStructure{Command: "stat", Args: []string{"-c%s", "/var/lib/imageloader/lacros/v1/image.squash"}}
	runDDCommand            = RunCommandStructure{Command: "dd", Args: []string{"if=/dev/zero", "bs=1", "count=3996", "seek=100", "of=/var/lib/imageloader/lacros/v1/image.squash"}}
	runVerityCommand        = RunCommandStructure{Command: "verity", Args: []string{"mode=create", "alg=sha256", "payload=/var/lib/imageloader/lacros/v1/image.squash", "payload_blocks=1", "hashtree=/var/lib/imageloader/lacros/v1/hashtree", "salt=random", ">", "/var/lib/imageloader/lacros/v1/table"}}
	runMeowHashTreeCommand  = RunCommandStructure{Command: "cat", Args: []string{"/var/lib/imageloader/lacros/v1/hashtree", ">>", "/var/lib/imageloader/lacros/v1/image.squash"}}
	getImageHashCommand     = RunCommandStructure{Command: "sha256sum", Args: []string{"/var/lib/imageloader/lacros/v1/image.squash", "|", "cut", "-d' '", "-f1"}}
	getTableHashCommand     = RunCommandStructure{Command: "sha256sum", Args: []string{"/var/lib/imageloader/lacros/v1/table", "|", "cut", "-d' '", "-f1"}}
	writeImgLdrCommand      = RunCommandStructure{Command: "echo", Args: []string{"'" + string(json_data) + "'", ">", "/var/lib/imageloader/lacros/v1/imageloader.json"}}
	writeManifestCommand    = RunCommandStructure{Command: "echo", Args: []string{"'" + string(component_json_data) + "'", ">", "/var/lib/imageloader/lacros/v1/manifest.json"}}
	writePublishCommand     = RunCommandStructure{Command: "echo", Args: []string{"'v1'", ">", "/var/lib/imageloader/lacros/latest-version"}}
	chownCommand            = RunCommandStructure{Command: "chown", Args: []string{"-R", "chronos:chronos", "/home/chronos/cros-components"}}
	chmodCommand            = RunCommandStructure{Command: "chmod", Args: []string{"-R", "0755", "/home/chronos/cros-components"}}
)

// CUSTOM OVERWRITE COMMANDS
var (
	customOverwriteCreateLaCrOSDirsCommand = CreateDirsStructure{Dirs: []string{"/home/chronos/cros-components/v1"}}
	customOverwriteCopyLaCrOSImageCommand  = CopyCommandStructure{Source: "path/to/image/lacros_compressed.squash", Dest: "/home/chronos/cros-components/v1/image.squash"}
	customOverwriteRunStatCommand          = RunCommandStructure{Command: "stat", Args: []string{"-c%s", "/home/chronos/cros-components/v1/image.squash"}}
	customOverwriteRunDDCommand            = RunCommandStructure{Command: "dd", Args: []string{"if=/dev/zero", "bs=1", "count=3996", "seek=100", "of=/home/chronos/cros-components/v1/image.squash"}}
	customOverwriteRunVerityCommand        = RunCommandStructure{Command: "verity", Args: []string{"mode=create", "alg=sha256", "payload=/home/chronos/cros-components/v1/image.squash", "payload_blocks=1", "hashtree=/home/chronos/cros-components/v1/hashtree", "salt=random", ">", "/home/chronos/cros-components/v1/table"}}
	customOverwriteRunMeowHashTreeCommand  = RunCommandStructure{Command: "cat", Args: []string{"/home/chronos/cros-components/v1/hashtree", ">>", "/home/chronos/cros-components/v1/image.squash"}}
	customOverwriteGetImageHashCommand     = RunCommandStructure{Command: "sha256sum", Args: []string{"/home/chronos/cros-components/v1/image.squash", "|", "cut", "-d' '", "-f1"}}
	customOverwriteGetTableHashCommand     = RunCommandStructure{Command: "sha256sum", Args: []string{"/home/chronos/cros-components/v1/table", "|", "cut", "-d' '", "-f1"}}
	customOverwriteWriteImgLdrCommand      = RunCommandStructure{Command: "echo", Args: []string{"'" + string(json_data) + "'", ">", "/home/chronos/cros-components/v1/imageloader.json"}}
	customOverwriteWriteManifestCommand    = RunCommandStructure{Command: "echo", Args: []string{"'" + string(component_json_data) + "'", ">", "/home/chronos/cros-components/v1/manifest.json"}}
	customOverwriteWritePublishCommand     = RunCommandStructure{Command: "echo", Args: []string{"'v1'", ">", "/var/lib/imageloader/lacros/latest-version"}}
)

func TestLaCrosStateTransitions(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	ls := service.NewLaCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		nil,
		"",
		"")

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewLaCrOSInitState(&ls)

	gomock.InOrder(
		getCopyDataCommand(sam, copyMetadataCommand).Return(nil),
		getRunCmdCommand(sam, runMeowMetadataCommand).Return(`{"content": {"version": "v1"}}`, nil),
		getCreateDirCommand(sam, createLaCrOSDirsCommand).Return(nil),
		getCopyDataCommand(sam, copyLaCrOSImageCommand).Return(nil),
		getRunCmdCommand(sam, runStatCommand).Return(" 100 ", nil),
		getRunCmdCommand(sam, runDDCommand).Return("", nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed init state: %v", err)
	}
	// INSTALL
	st = st.Next()

	gomock.InOrder(
		getRunCmdCommand(sam, runVerityCommand).Return("", nil),
		getRunCmdCommand(sam, runMeowHashTreeCommand).Return("", nil),
		getRunCmdCommand(sam, getImageHashCommand).Return("image_hash", nil),
		getRunCmdCommand(sam, getTableHashCommand).Return("table_hash", nil),
		getRunCmdCommand(sam, writeImgLdrCommand).Return("", nil),
		getRunCmdCommand(sam, writeManifestCommand).Return("", nil),
		getRunCmdCommand(sam, writePublishCommand).Return("", nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed install state: %v", err)
	}

	// Verify
	st = st.Next()

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed verify state: %v", err)
	}

	// Check state completion
	if st.Next() != nil {
		t.Fatalf("verify should be the last step")
	}
}

func TestLaCrosStateTransitionsWithOverride(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	ls := service.NewLaCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		nil,
		"",
		"/home/chronos/cros-components")

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewLaCrOSInitState(&ls)

	gomock.InOrder(
		getCopyDataCommand(sam, copyMetadataCommand).Return(nil),
		getRunCmdCommand(sam, runMeowMetadataCommand).Return(`{"content": {"version": "v1"}}`, nil),
		getCreateDirCommand(sam, customOverwriteCreateLaCrOSDirsCommand).Return(nil),
		getCopyDataCommand(sam, customOverwriteCopyLaCrOSImageCommand).Return(nil),
		getRunCmdCommand(sam, customOverwriteRunStatCommand).Return(" 100 ", nil),
		getRunCmdCommand(sam, customOverwriteRunDDCommand).Return("", nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed init state: %v", err)
	}
	// INSTALL
	st = st.Next()

	gomock.InOrder(
		getRunCmdCommand(sam, customOverwriteRunVerityCommand).Return("", nil),
		getRunCmdCommand(sam, customOverwriteRunMeowHashTreeCommand).Return("", nil),
		getRunCmdCommand(sam, customOverwriteGetImageHashCommand).Return("image_hash", nil),
		getRunCmdCommand(sam, customOverwriteGetTableHashCommand).Return("table_hash", nil),
		getRunCmdCommand(sam, customOverwriteWriteImgLdrCommand).Return("", nil),
		getRunCmdCommand(sam, customOverwriteWriteManifestCommand).Return("", nil),
		getRunCmdCommand(sam, customOverwriteWritePublishCommand).Return("", nil),
		getRunCmdCommand(sam, chownCommand).Return("", nil),
		getRunCmdCommand(sam, chmodCommand).Return("", nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed install state: %v", err)
	}
}

func TestLaCrosStateDoesNotExtendAlignment(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	ls := service.NewLaCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		nil,
		"",
		"")

	ctx := context.Background()

	// INIT STATE
	st := state_machine.NewLaCrOSInitState(&ls)

	gomock.InOrder(
		getCopyDataCommand(sam, copyMetadataCommand).Return(nil),
		getRunCmdCommand(sam, runMeowMetadataCommand).Return(`{"content": {"version": "v1"}}`, nil),
		getCreateDirCommand(sam, createLaCrOSDirsCommand).Return(nil),
		getCopyDataCommand(sam, copyLaCrOSImageCommand).Return(nil),
		getRunCmdCommand(sam, runStatCommand).Return(" 4096 ", nil),
		// Ensure dd doesn't run if value is multiple of 4096
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed init state: %v", err)
	}
}

func getCreateDirCommand(sam *mock_common_utils.MockServiceAdapterInterface, s CreateDirsStructure) *gomock.Call {
	return sam.EXPECT().CreateDirectories(gomock.Any(), gomock.Eq(s.Dirs))
}

func getCopyDataCommand(sam *mock_common_utils.MockServiceAdapterInterface, s CopyCommandStructure) *gomock.Call {
	return sam.EXPECT().CopyData(gomock.Any(), gomock.Eq(s.Source), gomock.Eq(s.Dest))
}

func getRunCmdCommand(sam *mock_common_utils.MockServiceAdapterInterface, s RunCommandStructure) *gomock.Call {
	return sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq(s.Command), gomock.Eq(s.Args))
}
