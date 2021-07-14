// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/info"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/mock_services"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services/ashservice"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services/crosservice"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services/lacrosservice"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"testing"

	"github.com/golang/mock/gomock"
	conf "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
)

func TestCrosInstallStateTransitions(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_services.NewMockServiceAdapterInterface(ctrl)

	cs := crosservice.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		false,
		[]*api.InstallCrosRequest_DLCSpec{{Id: "1"}},
	)

	ctx := context.Background()

	// INSTALL
	st := cs.GetFirstState()

	// Serial Portion
	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s"})).Return(fmt.Sprintf("root%s", info.PartitionNumRootA), nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s", "-d"})).Return("root_disk", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"ui"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"update-engine"})).Return("", nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq(info.DlcLibDir)).Return(true, nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"dlcservice"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-f", "/var/cache/dlc/*/*/dlc_b/verified"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("start"), gomock.Eq([]string{"dlcservice"})).Return("", nil),
	)
	// Concurrent portion
	sam.EXPECT().CopyData(gomock.Any(), gomock.Any()).Return("1", nil).AnyTimes()
	sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("curl"), gomock.Eq([]string{"1", "|", "gzip -d", "|", "dd of=root_diskroot5 obs=2M"})).Times(1).Return("", nil)
	sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("curl"), gomock.Eq([]string{"1", "|", "gzip -d", "|", "dd of=root_diskroot4 obs=2M"})).Times(1).Return("", nil)
	// Serial Portion
	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq(""), gomock.Eq([]string{
			"tmpmnt=$(mktemp -d)",
			"&&",
			"mount -o ro root_diskroot5 ${tmpmnt}",
			"&&",
			"${tmpmnt}/postinst root_diskroot5",
			"&&",
			"{ umount ${tmpmnt} || true; }",
			"&&",
			"{ rmdir ${tmpmnt} || true; }"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("crossystem"), gomock.Eq([]string{"clear_tpm_owner_request=1"})).Return("", nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed install state: %v", err)
	}

	// POST INSTALL
	st = st.Next()

	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("echo"), gomock.Eq([]string{"'fast keepimg'", ">", "/mnt/stateful_partition/factory_install_reset"})).Return("", nil),
		sam.EXPECT().Restart(gomock.Any()).Return(nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"ui"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"update-engine"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq(""), gomock.Eq([]string{"rm -rf /mnt/stateful_partition/.update_available /mnt/stateful_partition/var_new /mnt/stateful_partition/dev_image_new", "&&", "curl 1 | tar --ignore-command-error --overwrite --directory=/mnt/stateful_partition -xzf -", "&&", "echo -n clobber > /mnt/stateful_partition/.update_available"})).Return("", nil),
		sam.EXPECT().Restart(gomock.Any()).Return(nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed post-install state: %v", err)
	}

	// VERIFY (Currently empty)
	st = st.Next()

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed verify state: %v", err)
	}

	//PROVISION DLC
	st = st.Next()

	// Serial Portion
	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"dlcservice"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s"})).Return(fmt.Sprintf("root%s", info.PartitionNumRootA), nil),
	)
	// Concurrent Portion
	// Return not verfied so we can test full case:
	sam.EXPECT().PathExists(gomock.Any(), "/var/lib/dlcservice/dlc/1/dlc_a/verified").Return(false, nil)
	sam.EXPECT().RunCmd(gomock.Any(), "", []string{"mkdir", "-p", "/var/cache/dlc/1/package/dlc_a", "&&", "curl", "--output", "/var/cache/dlc/1/package/dlc_a/dlc.img", "1"}).Return("", nil)
	sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("start"), gomock.Eq([]string{"dlcservice"})).Times(1).Return("", nil)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed provision-dlc state: %v", err)
	}

	if st.Next() != nil {
		t.Fatalf("provision should be the last step")
	}
}

func TestInstallPostInstallFailureCausesReversal(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_services.NewMockServiceAdapterInterface(ctrl)

	cs := crosservice.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		false,
		[]*api.InstallCrosRequest_DLCSpec{{Id: "1"}},
	)

	ctx := context.Background()

	// INSTALL
	st := cs.GetFirstState()

	// Serial Portion
	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s"})).Return(fmt.Sprintf("root%s", info.PartitionNumRootA), nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s", "-d"})).Return("root_disk", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"ui"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"update-engine"})).Return("", nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq(info.DlcLibDir)).Return(true, nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"dlcservice"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-f", "/var/cache/dlc/*/*/dlc_b/verified"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("start"), gomock.Eq([]string{"dlcservice"})).Return("", nil),
	)
	// Concurrent portion
	sam.EXPECT().CopyData(gomock.Any(), gomock.Any()).Return("1", nil).AnyTimes()
	sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("curl"), gomock.Eq([]string{"1", "|", "gzip -d", "|", "dd of=root_diskroot5 obs=2M"})).Times(1).Return("", nil)
	sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("curl"), gomock.Eq([]string{"1", "|", "gzip -d", "|", "dd of=root_diskroot4 obs=2M"})).Times(1).Return("", nil)
	// Serial Portion
	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq(""), gomock.Eq([]string{
			"tmpmnt=$(mktemp -d)",
			"&&",
			"mount -o ro root_diskroot5 ${tmpmnt}",
			"&&",
			"${tmpmnt}/postinst root_diskroot5",
			"&&",
			"{ umount ${tmpmnt} || true; }",
			"&&",
			"{ rmdir ${tmpmnt} || true; }"})).Return("", fmt.Errorf("postinstall error")),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-rf", "/mnt/stateful_partition/var_new", "/mnt/stateful_partition/dev_image_new", "/mnt/stateful_partition/.update_available"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("/postinst"), gomock.Eq([]string{"root_diskroot3", "2>&1"})).Return("", nil),
	)

	if err := st.Execute(ctx); err.Error() != "failed to set next kernel, postinstall error" {
		t.Fatalf("expected specific error, instead got: %v", err)
	}
}

func TestInstallClearTPMFailureCausesReversal(t *testing.T) {

	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_services.NewMockServiceAdapterInterface(ctrl)

	cs := crosservice.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		false,
		[]*api.InstallCrosRequest_DLCSpec{{Id: "1"}},
	)

	ctx := context.Background()

	// INSTALL
	st := cs.GetFirstState()

	// Serial Portion
	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s"})).Return(fmt.Sprintf("root%s", info.PartitionNumRootA), nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s", "-d"})).Return("root_disk", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"ui"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"update-engine"})).Return("", nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq(info.DlcLibDir)).Return(true, nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"dlcservice"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-f", "/var/cache/dlc/*/*/dlc_b/verified"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("start"), gomock.Eq([]string{"dlcservice"})).Return("", nil),
	)
	// Concurrent portion
	sam.EXPECT().CopyData(gomock.Any(), gomock.Any()).Return("1", nil).AnyTimes()
	sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("curl"), gomock.Eq([]string{"1", "|", "gzip -d", "|", "dd of=root_diskroot5 obs=2M"})).Times(1).Return("", nil)
	sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("curl"), gomock.Eq([]string{"1", "|", "gzip -d", "|", "dd of=root_diskroot4 obs=2M"})).Times(1).Return("", nil)
	// Serial Portion
	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq(""), gomock.Eq([]string{
			"tmpmnt=$(mktemp -d)",
			"&&",
			"mount -o ro root_diskroot5 ${tmpmnt}",
			"&&",
			"${tmpmnt}/postinst root_diskroot5",
			"&&",
			"{ umount ${tmpmnt} || true; }",
			"&&",
			"{ rmdir ${tmpmnt} || true; }"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("crossystem"), gomock.Eq([]string{"clear_tpm_owner_request=1"})).Return("", fmt.Errorf("clear TPM error")),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-rf", "/mnt/stateful_partition/var_new", "/mnt/stateful_partition/dev_image_new", "/mnt/stateful_partition/.update_available"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("/postinst"), gomock.Eq([]string{"root_diskroot3", "2>&1"})).Return("", nil),
	)

	if err := st.Execute(ctx); err.Error() != "failed to clear TPM, clear TPM error" {
		t.Fatalf("expected specific error, instead got: %v", err)
	}
}

func TestPostInstallStatePreservesStatefulWhenRequested(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_services.NewMockServiceAdapterInterface(ctrl)

	cs := crosservice.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		true, // <- preserve stateful
		[]*api.InstallCrosRequest_DLCSpec{},
	)

	ctx := context.Background()

	// Install -> PostInstall
	st := cs.GetFirstState().Next()

	gomock.InOrder(
		// Delete steps elided due to preserve stateful
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"ui"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"update-engine"})).Return("", nil),
		sam.EXPECT().CopyData(gomock.Any(), gomock.Eq("path/to/image/stateful.tzg")).Return("url", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq(""), gomock.Eq([]string{"rm -rf /mnt/stateful_partition/.update_available /mnt/stateful_partition/var_new /mnt/stateful_partition/dev_image_new", "&&", "curl url | tar --ignore-command-error --overwrite --directory=/mnt/stateful_partition -xzf -", "&&", "echo -n clobber > /mnt/stateful_partition/.update_available"})).Return("", nil),
		sam.EXPECT().Restart(gomock.Any()).Return(nil),
	)

	// Nothing should be run, so no need to use mock expect
	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed post-install state: %v", err)
	}
}

func TestPostInstallStatefulFailsGetsReversed(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_services.NewMockServiceAdapterInterface(ctrl)

	cs := crosservice.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		true, // <- preserve stateful
		[]*api.InstallCrosRequest_DLCSpec{},
	)

	ctx := context.Background()

	// Install -> PostInstall
	st := cs.GetFirstState().Next()

	gomock.InOrder(
		// Delete steps elided due to preserve stateful
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"ui"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"update-engine"})).Return("", nil),
		// Simulated error:
		sam.EXPECT().CopyData(gomock.Any(), gomock.Eq("path/to/image/stateful.tzg")).Return("", errors.New("some copy error")),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-rf", "/mnt/stateful_partition/var_new", "/mnt/stateful_partition/dev_image_new", "/mnt/stateful_partition/.update_available"})).Return("", nil),
	)

	// Nothing should be run, so no need to use mock expect
	if err := st.Execute(ctx); err.Error() != "failed to provision stateful, failed to install stateful partition, failed to get GS Cache URL, some copy error" {
		t.Fatalf("Post install should've failed with specific error, instead got: %v", err)
	}

}

func TestProvisionDLCWithEmptyDLCsDoesNotExecute(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_services.NewMockServiceAdapterInterface(ctrl)

	cs := crosservice.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		false,
		[]*api.InstallCrosRequest_DLCSpec{},
	)

	ctx := context.Background()

	// Install -> PostInstall -> Verify -> ProvisionDLC
	st := cs.GetFirstState().Next().Next().Next()

	// Nothing should be run, so no need to use mock expect
	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed provision-dlc state: %v", err)
	}
}

func TestProvisionDLCWhenVerifyIsTrueDoesNotExecuteInstall(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_services.NewMockServiceAdapterInterface(ctrl)

	cs := crosservice.NewCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		false,
		[]*api.InstallCrosRequest_DLCSpec{{Id: "1"}},
	)

	ctx := context.Background()

	// Install -> PostInstall -> Verify -> ProvisionDLC
	st := cs.GetFirstState().Next().Next().Next()

	// Serial Portion
	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"dlcservice"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s"})).Return(fmt.Sprintf("root%s", info.PartitionNumRootA), nil),
	)
	// Concurrent Portion
	// Return verfied so install stops there
	sam.EXPECT().PathExists(gomock.Any(), "/var/lib/dlcservice/dlc/1/dlc_a/verified").Return(true, nil)
	sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("start"), gomock.Eq([]string{"dlcservice"})).Times(1).Return("", nil)

	// Nothing should be run, so no need to use mock expect
	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed provision-dlc state: %v", err)
	}
}

func TestLaCrOSInstallStateTransitions(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_services.NewMockServiceAdapterInterface(ctrl)

	cs := lacrosservice.NewLaCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		&lacrosservice.LaCrOSMetadata{Content: struct {
			Version string "json:\"version\""
		}{"v1"}},
	)

	ctx := context.Background()

	// INSTALL
	st := cs.GetFirstState()

	gomock.InOrder(
		sam.EXPECT().CopyData(gomock.Any(), gomock.Eq("path/to/image/lacros_compressed.squash")).Return("first.url", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq(""), gomock.Eq([]string{"mkdir", "-p", "/var/lib/imageloader/lacros/v1", "&&", "curl", "first.url", "--output", "/var/lib/imageloader/lacros/v1/image.squash"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stat"), gomock.Eq([]string{"-c%s", "/var/lib/imageloader/lacros/v1/image.squash"})).Return(" 100 ", nil),
		// Ensure dd runs if value isn't multiple of 4096:
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("dd"), gomock.Eq([]string{"if=/dev/zero", "bs=1", "count=3996", "seek=100", "of=/var/lib/imageloader/lacros/v1/image.squash"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("verity"), gomock.Eq([]string{"mode=create", "alg=sha256", "payload=/var/lib/imageloader/lacros/v1/image.squash", "payload_blocks=1", "hashtree=/var/lib/imageloader/lacros/v1/hashtree", "salt=random", ">", "/var/lib/imageloader/lacros/v1/table"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("cat"), gomock.Eq([]string{"/var/lib/imageloader/lacros/v1/hashtree", ">>", "/var/lib/imageloader/lacros/v1/image.squash"})).Return("", nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed install state: %v", err)
	}

	// POST INSTALL
	st = st.Next()

	json_data, err := json.MarshalIndent(struct {
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
	if err != nil {
		t.Fatalf("failed to marshal expected data, %v", err)
	}

	component_json_data, err := json.MarshalIndent(struct {
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
	if err != nil {
		t.Fatalf("failed to marshal expected component data, %v", err)
	}

	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("sha256sum"), gomock.Eq([]string{"/var/lib/imageloader/lacros/v1/image.squash", "|", "cut", "-d' '", "-f1"})).Return("image_hash", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("sha256sum"), gomock.Eq([]string{"/var/lib/imageloader/lacros/v1/table", "|", "cut", "-d' '", "-f1"})).Return("table_hash", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("echo"), gomock.Eq([]string{"'" + string(json_data) + "'", ">", "/var/lib/imageloader/lacros/v1/imageloader.json"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("echo"), gomock.Eq([]string{"'" + string(component_json_data) + "'", ">", "/var/lib/imageloader/lacros/v1/manifest.json"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("echo"), gomock.Eq([]string{"'v1'", ">", "/var/lib/imageloader/lacros/latest-version"})).Return("", nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed post-install state: %v", err)
	}

	// VERIFY (Currently empty)
	st = st.Next()

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed verify state: %v", err)
	}

	if st.Next() != nil {
		t.Fatalf("verify should be the last step")
	}
}

func TestLacrosAlignedDoesNotExtendAlignment(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_services.NewMockServiceAdapterInterface(ctrl)

	cs := lacrosservice.NewLaCrOSServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
		&lacrosservice.LaCrOSMetadata{Content: struct {
			Version string "json:\"version\""
		}{"v1"}},
	)

	ctx := context.Background()

	// INSTALL
	st := cs.GetFirstState()

	gomock.InOrder(
		sam.EXPECT().CopyData(gomock.Any(), gomock.Eq("path/to/image/lacros_compressed.squash")).Return("first.url", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq(""), gomock.Eq([]string{"mkdir", "-p", "/var/lib/imageloader/lacros/v1", "&&", "curl", "first.url", "--output", "/var/lib/imageloader/lacros/v1/image.squash"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stat"), gomock.Eq([]string{"-c%s", "/var/lib/imageloader/lacros/v1/image.squash"})).Return(" 4096 ", nil),
		// Ensure dd doesn't run if value is multiple of 4096:
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("verity"), gomock.Eq([]string{"mode=create", "alg=sha256", "payload=/var/lib/imageloader/lacros/v1/image.squash", "payload_blocks=1", "hashtree=/var/lib/imageloader/lacros/v1/hashtree", "salt=random", ">", "/var/lib/imageloader/lacros/v1/table"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("cat"), gomock.Eq([]string{"/var/lib/imageloader/lacros/v1/hashtree", ">>", "/var/lib/imageloader/lacros/v1/image.squash"})).Return("", nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed install state: %v", err)
	}
}

func TestAshInstallStateTransitions(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_services.NewMockServiceAdapterInterface(ctrl)

	as := ashservice.NewAshServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
	)

	ctx := context.Background()

	// PREPARE
	st := as.GetFirstState()

	gomock.InOrder(
		sam.EXPECT().DeleteDirectory(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy")).Return(nil),
		sam.EXPECT().CreateDirectories(gomock.Any(), gomock.Eq([]string{"/tmp/_provisioning_service_chrome_deploy"})).Return(nil),
		sam.EXPECT().CopyData(gomock.Any(), "path/to/image").Return("image_url", nil),
		sam.EXPECT().RunCmd(gomock.Any(), "", []string{"curl", "image_url", "|", "tar", "--ignore-command-error", "--overwrite", "--preserve-permissions", "--directory=/tmp/_provisioning_service_chrome_deploy", "-xf", "-"}).Return("", nil),
		sam.EXPECT().CreateDirectories(gomock.Any(), gomock.Eq([]string{"/opt/google/chrome", "/usr/local/autotest/deps/chrome_test/test_src/out/Release/", "/usr/local/libexec/chrome-binary-tests/"})).Return(nil),
		sam.EXPECT().RunCmd(gomock.Any(), "stop", []string{"ui"}).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), "lsof", []string{"/opt/google/chrome/chrome"}).Return("", errors.New("chrome is in use!")),
		sam.EXPECT().RunCmd(gomock.Any(), "pkill", []string{"'chrome|session_manager'"}).Return("", nil),
		// Make first kill soft fail so we test retry:
		sam.EXPECT().RunCmd(gomock.Any(), "lsof", []string{"/opt/google/chrome/chrome"}).Return("", errors.New("chrome is ***still*** in use!")),
		sam.EXPECT().RunCmd(gomock.Any(), "pkill", []string{"'chrome|session_manager'"}).Return("", nil),
		// Now we let it progress
		sam.EXPECT().RunCmd(gomock.Any(), "lsof", []string{"/opt/google/chrome/chrome"}).Return("", nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed prepare state: %v", err)
	}

	// INSTALL
	st = st.Next()

	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), "mount", []string{"-o", "remount,rw", "/"}).Return("", nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/ash_shell")).Return(true, nil),
		sam.EXPECT().RunCmd(gomock.Any(), "rsync", []string{"-av", "/tmp/_provisioning_service_chrome_deploy/ash_shell", "/opt/google/chrome"}).Return("", nil),
		// For all items after we make them exist so we don't need to double every item (we assume that the test isn't breakable here):
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/aura_demo")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/chrome")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/chrome-wrapper")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/chrome.pak")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/chrome_100_percent.pak")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/chrome_200_percent.pak")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/content_shell")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/content_shell.pak")).Return(false, nil),
		// Testing this one specifically as it should map to the designated folder rather than the top-most:
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/extensions/")).Return(true, nil),
		sam.EXPECT().RunCmd(gomock.Any(), "rsync", []string{"-av", "/tmp/_provisioning_service_chrome_deploy/extensions/", "/opt/google/chrome/extensions"}).Return("", nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/lib/*.so")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/libffmpegsumo.so")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/libpdf.so")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/libppGoogleNaClPluginChrome.so")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/libosmesa.so")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/libwidevinecdmadapter.so")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/libwidevinecdm.so")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/locales/")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/nacl_helper_bootstrap")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/nacl_irt_*.nexe")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/nacl_helper")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/resources/")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/resources.pak")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/xdg-settings")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/*.png")).Return(false, nil),

		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/*test")).Return(true, nil),
		sam.EXPECT().RunCmd(gomock.Any(), "rsync", []string{"-av", "/tmp/_provisioning_service_chrome_deploy/*test", "/usr/local/autotest/deps/chrome_test/test_src/out/Release"}).Return("", nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/*test")).Return(true, nil),
		sam.EXPECT().RunCmd(gomock.Any(), "rsync", []string{"-av", "/tmp/_provisioning_service_chrome_deploy/*test", "/usr/local/libexec/chrome-binary-tests"}).Return("", nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/*tests")).Return(false, nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy/*tests")).Return(false, nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed install state: %v", err)
	}

	// POST INSTALL
	st = st.Next()

	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), "killall", []string{"-HUP", "dbus-daemon"}).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), "start", []string{"ui"}).Return("", nil),
		sam.EXPECT().DeleteDirectory(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy")).Return(nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed post-install state: %v", err)
	}

	if st.Next() != nil {
		t.Fatalf("provision should be the last step")
	}
}

func TestPkillOnlyRunsForTenSeconds(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_services.NewMockServiceAdapterInterface(ctrl)

	as := ashservice.NewAshServiceFromExistingConnection(
		sam,
		&conf.StoragePath{
			HostType: conf.StoragePath_GS,
			Path:     "path/to/image",
		},
	)

	ctx := context.Background()

	// PREPARE
	st := as.GetFirstState()

	gomock.InOrder(
		sam.EXPECT().DeleteDirectory(gomock.Any(), gomock.Eq("/tmp/_provisioning_service_chrome_deploy")).Return(nil),
		sam.EXPECT().CreateDirectories(gomock.Any(), gomock.Eq([]string{"/tmp/_provisioning_service_chrome_deploy"})).Return(nil),
		sam.EXPECT().CopyData(gomock.Any(), "path/to/image").Return("image_url", nil),
		sam.EXPECT().RunCmd(gomock.Any(), "", []string{"curl", "image_url", "|", "tar", "--ignore-command-error", "--overwrite", "--preserve-permissions", "--directory=/tmp/_provisioning_service_chrome_deploy", "-xf", "-"}).Return("", nil),
		sam.EXPECT().CreateDirectories(gomock.Any(), gomock.Eq([]string{"/opt/google/chrome", "/usr/local/autotest/deps/chrome_test/test_src/out/Release/", "/usr/local/libexec/chrome-binary-tests/"})).Return(nil),
		sam.EXPECT().RunCmd(gomock.Any(), "stop", []string{"ui"}).Return("", nil),
	)

	sam.EXPECT().RunCmd(gomock.Any(), "lsof", []string{"/opt/google/chrome/chrome"}).Return("", errors.New("chrome is in use!")).AnyTimes()
	sam.EXPECT().RunCmd(gomock.Any(), "pkill", []string{"'chrome|session_manager'"}).Return("", nil).AnyTimes()

	if err := st.Execute(ctx); err == nil {
		t.Fatalf("prepare should've failed!")
	}
}
