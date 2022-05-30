// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package provisionserver

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/info"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/mock_services"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services/ashservice"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services/crosservice"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services/firmwareservice"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services/lacrosservice"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"path/filepath"
	"strings"
	"testing"

	"github.com/golang/mock/gomock"
	conf "go.chromium.org/chromiumos/config/go"
	build_api "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
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
		nil,
		false,
		[]*api.InstallCrosRequest_DLCSpec{{Id: "1"}},
	)

	ctx := context.Background()

	// INSTALL
	st := cs.GetFirstState()

	// Serial Portion
	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("touch"), gomock.Eq([]string{"/var/tmp/provision_failed"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s"})).Return(fmt.Sprintf("root%s", info.PartitionNumRootA), nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s", "-d"})).Return("root_disk", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"ui"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"update-engine"})).Return("", nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq(info.DlcLibDir)).Return(true, nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"dlcservice"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-f", "/var/cache/dlc/*/*/dlc_b/verified"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("start"), gomock.Eq([]string{"dlcservice"})).Return("", nil),
		sam.EXPECT().PipeData(gomock.Any(), gomock.Eq("gs://path/to/image/full_dev_part_KERN.bin.gz"),
			gomock.Eq("gzip -d | dd of=root_diskroot4 obs=2M \npipestatus=(\"${PIPESTATUS[@]}\")\nif [[ \"${pipestatus[0]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Fetching path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[1]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Decompressing path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[2]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Writing to root_diskroot4 failed.\" >&2\n  exit 1\nfi")).Times(1).Return(nil),
		sam.EXPECT().PipeData(gomock.Any(), gomock.Eq("gs://path/to/image/full_dev_part_ROOT.bin.gz"),
			gomock.Eq("gzip -d | dd of=root_diskroot5 obs=2M \npipestatus=(\"${PIPESTATUS[@]}\")\nif [[ \"${pipestatus[0]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Fetching path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[1]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Decompressing path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[2]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Writing to root_diskroot5 failed.\" >&2\n  exit 1\nfi")).Times(1).Return(nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("mktemp"), gomock.Eq([]string{"-d"})).Return("temporary_dir", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("mount"), gomock.Eq([]string{"-o", "ro", "root_diskroot5", "temporary_dir"})),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("temporary_dir/postinst"), gomock.Eq([]string{"root_diskroot5"})),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("umount"), gomock.Eq([]string{"temporary_dir"})),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rmdir"), gomock.Eq([]string{"temporary_dir"})),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("cat"), gomock.Eq([]string{"/etc/lsb-release"})).Return("CHROMEOS_RELEASE_BOARD=(not_raven)", nil),
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
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-rf", "/mnt/stateful_partition/.update_available", "/mnt/stateful_partition/var_new", "/mnt/stateful_partition/dev_image_new"})).Return("", nil),
		sam.EXPECT().PipeData(gomock.Any(), gomock.Eq("gs://path/to/image/stateful.tgz"), gomock.Eq("tar --ignore-command-error --overwrite --directory=/mnt/stateful_partition -xzf -")).Return(nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("echo"), []string{"-n", "clobber", ">", "/mnt/stateful_partition/.update_available"}).Return("", nil),
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
	sam.EXPECT().CreateDirectories(gomock.Any(), gomock.Eq([]string{"/var/cache/dlc/1/package/dlc_a"})).Return(nil)
	sam.EXPECT().CopyData(gomock.Any(), gomock.Any(), gomock.Eq("/var/cache/dlc/1/package/dlc_a/dlc.img")).Return(nil)
	sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("start"), gomock.Eq([]string{"dlcservice"})).Times(1).Return("", nil)

	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("chown"), gomock.Eq([]string{"-R", "dlcservice:dlcservice", "/var/cache/dlc"})),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("chmod"), gomock.Eq([]string{"-R", "0755", "/var/cache/dlc"})),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed provision-dlc state: %v", err)
	}

	//INSTALL MINIOS
	st = st.Next()

	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s"})).Return(fmt.Sprintf("root%s", info.PartitionNumRootA), nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s", "-d"})).Return("root_disk", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("cgpt"), gomock.Eq([]string{"show", "-t", "root_disk", "9"})).Return("not 09845860-705F-4BB5-B16C-8A8A099CAF52", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("cgpt"), gomock.Eq([]string{"show", "-t", "root_disk", "10"})).Return("not 09845860-705F-4BB5-B16C-8A8A099CAF52", nil),
		sam.EXPECT().PipeData(gomock.Any(), gomock.Eq("gs://path/to/image/full_dev_part_MINIOS.bin.gz"),
			gomock.Eq("gzip -d | dd of=root_diskroot9 obs=2M \npipestatus=(\"${PIPESTATUS[@]}\")\nif [[ \"${pipestatus[0]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Fetching path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[1]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Decompressing path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[2]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Writing to root_diskroot9 failed.\" >&2\n  exit 1\nfi")).Times(1).Return(nil),
		sam.EXPECT().PipeData(gomock.Any(), gomock.Eq("gs://path/to/image/full_dev_part_MINIOS.bin.gz"),
			gomock.Eq("gzip -d | dd of=root_diskroot10 obs=2M \npipestatus=(\"${PIPESTATUS[@]}\")\nif [[ \"${pipestatus[0]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Fetching path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[1]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Decompressing path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[2]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Writing to root_diskroot10 failed.\" >&2\n  exit 1\nfi")).Times(1).Return(nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed install-minios state: %v", err)
	}

	if st.Next() != nil {
		t.Fatalf("installminios should be the last step")
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
		nil,
		false,
		[]*api.InstallCrosRequest_DLCSpec{{Id: "1"}},
	)

	ctx := context.Background()

	// INSTALL
	st := cs.GetFirstState()

	// Serial Portion
	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("touch"), gomock.Eq([]string{"/var/tmp/provision_failed"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s"})).Return(fmt.Sprintf("root%s", info.PartitionNumRootA), nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s", "-d"})).Return("root_disk", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"ui"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"update-engine"})).Return("", nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq(info.DlcLibDir)).Return(true, nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"dlcservice"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-f", "/var/cache/dlc/*/*/dlc_b/verified"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("start"), gomock.Eq([]string{"dlcservice"})).Return("", nil),
		sam.EXPECT().PipeData(gomock.Any(), gomock.Eq("gs://path/to/image/full_dev_part_KERN.bin.gz"),
			gomock.Eq("gzip -d | dd of=root_diskroot4 obs=2M \npipestatus=(\"${PIPESTATUS[@]}\")\nif [[ \"${pipestatus[0]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Fetching path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[1]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Decompressing path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[2]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Writing to root_diskroot4 failed.\" >&2\n  exit 1\nfi")).Times(1).Return(nil),
		sam.EXPECT().PipeData(gomock.Any(), gomock.Eq("gs://path/to/image/full_dev_part_ROOT.bin.gz"),
			gomock.Eq("gzip -d | dd of=root_diskroot5 obs=2M \npipestatus=(\"${PIPESTATUS[@]}\")\nif [[ \"${pipestatus[0]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Fetching path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[1]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Decompressing path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[2]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Writing to root_diskroot5 failed.\" >&2\n  exit 1\nfi")).Times(1).Return(nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("mktemp"), gomock.Eq([]string{"-d"})).Return("temporary_dir", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("mount"), gomock.Eq([]string{"-o", "ro", "root_diskroot5", "temporary_dir"})),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("temporary_dir/postinst"), gomock.Eq([]string{"root_diskroot5"})),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("umount"), gomock.Eq([]string{"temporary_dir"})),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rmdir"), gomock.Eq([]string{"temporary_dir"})).Return("", fmt.Errorf("postinstall error")),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-rf", "/mnt/stateful_partition/var_new", "/mnt/stateful_partition/dev_image_new", "/mnt/stateful_partition/.update_available"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("/postinst"), gomock.Eq([]string{"root_diskroot3", "2>&1"})).Return("", nil),
	)

	if err := st.Execute(ctx); err.Error() != "failed to set next kernel, failed to remove temporary directory, postinstall error" {
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
		nil,
		false,
		[]*api.InstallCrosRequest_DLCSpec{{Id: "1"}},
	)

	ctx := context.Background()

	// INSTALL
	st := cs.GetFirstState()

	// Serial Portion
	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("touch"), gomock.Eq([]string{"/var/tmp/provision_failed"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s"})).Return(fmt.Sprintf("root%s", info.PartitionNumRootA), nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rootdev"), gomock.Eq([]string{"-s", "-d"})).Return("root_disk", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"ui"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"update-engine"})).Return("", nil),
		sam.EXPECT().PathExists(gomock.Any(), gomock.Eq(info.DlcLibDir)).Return(true, nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"dlcservice"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-f", "/var/cache/dlc/*/*/dlc_b/verified"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("start"), gomock.Eq([]string{"dlcservice"})).Return("", nil),
		sam.EXPECT().PipeData(gomock.Any(), gomock.Eq("gs://path/to/image/full_dev_part_KERN.bin.gz"),
			gomock.Eq("gzip -d | dd of=root_diskroot4 obs=2M \npipestatus=(\"${PIPESTATUS[@]}\")\nif [[ \"${pipestatus[0]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Fetching path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[1]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Decompressing path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[2]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Writing to root_diskroot4 failed.\" >&2\n  exit 1\nfi")).Times(1).Return(nil),
		sam.EXPECT().PipeData(gomock.Any(), gomock.Eq("gs://path/to/image/full_dev_part_ROOT.bin.gz"),
			gomock.Eq("gzip -d | dd of=root_diskroot5 obs=2M \npipestatus=(\"${PIPESTATUS[@]}\")\nif [[ \"${pipestatus[0]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Fetching path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[1]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Decompressing path/to/image failed.\" >&2\n  exit 1\nelif [[ \"${pipestatus[2]}\" -ne 0 ]]; then\n  echo \"$(date --rfc-3339=seconds) ERROR: Writing to root_diskroot5 failed.\" >&2\n  exit 1\nfi")).Times(1).Return(nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("mktemp"), gomock.Eq([]string{"-d"})).Return("temporary_dir", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("mount"), gomock.Eq([]string{"-o", "ro", "root_diskroot5", "temporary_dir"})),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("temporary_dir/postinst"), gomock.Eq([]string{"root_diskroot5"})),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("umount"), gomock.Eq([]string{"temporary_dir"})),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rmdir"), gomock.Eq([]string{"temporary_dir"})),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("cat"), gomock.Eq([]string{"/etc/lsb-release"})).Return("CHROMEOS_RELEASE_BOARD=(not_raven)", nil),
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
		nil,
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
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-rf", "/mnt/stateful_partition/.update_available", "/mnt/stateful_partition/var_new", "/mnt/stateful_partition/dev_image_new"})).Return("", nil),
		sam.EXPECT().PipeData(gomock.Any(), gomock.Eq("gs://path/to/image/stateful.tgz"), gomock.Eq("tar --ignore-command-error --overwrite --directory=/mnt/stateful_partition -xzf -")).Return(nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("echo"), []string{"-n", "clobber", ">", "/mnt/stateful_partition/.update_available"}).Return("", nil),
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
		nil,
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
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-rf", "/mnt/stateful_partition/.update_available", "/mnt/stateful_partition/var_new", "/mnt/stateful_partition/dev_image_new"})).Return("", nil),
		sam.EXPECT().PipeData(gomock.Any(), gomock.Eq("gs://path/to/image/stateful.tgz"), gomock.Eq("tar --ignore-command-error --overwrite --directory=/mnt/stateful_partition -xzf -")).Return(errors.New("some copy error")),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-rf", "/mnt/stateful_partition/var_new", "/mnt/stateful_partition/dev_image_new", "/mnt/stateful_partition/.update_available"})).Return("", nil),
	)

	// Nothing should be run, so no need to use mock expect
	if err := st.Execute(ctx); err.Error() != "failed to provision stateful, failed to install stateful partition, some copy error" {
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
		nil,
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
		nil,
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

	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("chown"), gomock.Eq([]string{"-R", "dlcservice:dlcservice", "/var/cache/dlc"})),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("chmod"), gomock.Eq([]string{"-R", "0755", "/var/cache/dlc"})),
	)

	// Nothing should be run, so no need to use mock expect
	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed provision-dlc state: %v", err)
	}
}

func TestPostInstallOverwriteWhenSpecified(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sam := mock_services.NewMockServiceAdapterInterface(ctrl)

	cs := crosservice.NewCrOSServiceFromExistingConnection(
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
		[]*api.InstallCrosRequest_DLCSpec{{Id: "1"}},
	)

	ctx := context.Background()

	// Install -> PostInstall
	st := cs.GetFirstState().Next()

	gomock.InOrder(
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("echo"), gomock.Eq([]string{"'fast keepimg'", ">", "/mnt/stateful_partition/factory_install_reset"})).Return("", nil),
		sam.EXPECT().Restart(gomock.Any()).Return(nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"ui"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("stop"), gomock.Eq([]string{"update-engine"})).Return("", nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("rm"), gomock.Eq([]string{"-rf", "/mnt/stateful_partition/.update_available", "/mnt/stateful_partition/var_new", "/mnt/stateful_partition/dev_image_new"})).Return("", nil),
		sam.EXPECT().PipeData(gomock.Any(), gomock.Eq("gs://path/to/image/stateful.tgz"), gomock.Eq("tar --ignore-command-error --overwrite --directory=/mnt/stateful_partition -xzf -")).Return(nil),
		sam.EXPECT().RunCmd(gomock.Any(), gomock.Eq("echo"), []string{"-n", "clobber", ">", "/mnt/stateful_partition/.update_available"}).Return("", nil),
		sam.EXPECT().PipeData(gomock.Any(), gomock.Eq("path/to/image/overwite.tar"), gomock.Eq("tar xf - -C /")).Return(nil),
		sam.EXPECT().Restart(gomock.Any()).Return(nil),
	)

	if err := st.Execute(ctx); err != nil {
		t.Fatalf("failed post-install state: %v", err)
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
		"",
		"/var/lib/imageloader/lacros",
	)

	ctx := context.Background()

	// INSTALL
	st := cs.GetFirstState()

	gomock.InOrder(
		sam.EXPECT().CreateDirectories(gomock.Any(), gomock.Eq([]string{"/var/lib/imageloader/lacros/v1"})).Return(nil),
		sam.EXPECT().CopyData(gomock.Any(), gomock.Eq("path/to/image/lacros_compressed.squash"), gomock.Eq("/var/lib/imageloader/lacros/v1/image.squash")).Return(nil),
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
		"",
		"/var/lib/imageloader/lacros",
	)

	ctx := context.Background()

	// INSTALL
	st := cs.GetFirstState()

	gomock.InOrder(
		sam.EXPECT().CreateDirectories(gomock.Any(), gomock.Eq([]string{"/var/lib/imageloader/lacros/v1"})).Return(nil),
		sam.EXPECT().CopyData(gomock.Any(), gomock.Eq("path/to/image/lacros_compressed.squash"), gomock.Eq("/var/lib/imageloader/lacros/v1/image.squash")).Return(nil),
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
		sam.EXPECT().PipeData(gomock.Any(), "path/to/image", gomock.Eq("tar --ignore-command-error --overwrite --preserve-permissions --directory=/tmp/_provisioning_service_chrome_deploy -xf -")).Return(nil),
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
		sam.EXPECT().PipeData(gomock.Any(), "path/to/image", gomock.Eq("tar --ignore-command-error --overwrite --preserve-permissions --directory=/tmp/_provisioning_service_chrome_deploy -xf -")).Return(nil),
		sam.EXPECT().CreateDirectories(gomock.Any(), gomock.Eq([]string{"/opt/google/chrome", "/usr/local/autotest/deps/chrome_test/test_src/out/Release/", "/usr/local/libexec/chrome-binary-tests/"})).Return(nil),
		sam.EXPECT().RunCmd(gomock.Any(), "stop", []string{"ui"}).Return("", nil),
	)

	sam.EXPECT().RunCmd(gomock.Any(), "lsof", []string{"/opt/google/chrome/chrome"}).Return("", errors.New("chrome is in use!")).AnyTimes()
	sam.EXPECT().RunCmd(gomock.Any(), "pkill", []string{"'chrome|session_manager'"}).Return("", nil).AnyTimes()

	if err := st.Execute(ctx); err == nil {
		t.Fatalf("prepare should've failed!")
	}
}

func TestFirmwareProvisioningSSHStates(t *testing.T) {
	fakeGSPath := "gs://test-archive.tar.gz"
	fakeGSFilename := filepath.Base(fakeGSPath)

	apImageWithinArchive := "image.bin"
	ecImageWithinArchive := "ec.bin"
	pdImageWithinArchive := "pd.bin"
	imagesWithinArchive := strings.Join([]string{
		"foo",
		apImageWithinArchive,
		"bar",
		ecImageWithinArchive,
		"baz",
		pdImageWithinArchive,
	}, "\n") // as reported by tar

	makeRequest := func(main_rw, main_ro, ec_ro, pd_ro bool) *api.InstallFirmwareRequest {
		fakePayload := &build_api.FirmwarePayload{FirmwareImage: &build_api.FirmwarePayload_FirmwareImagePath{FirmwareImagePath: &conf.StoragePath{HostType: conf.StoragePath_GS, Path: fakeGSPath}}}
		FirmwareConfig := build_api.FirmwareConfig{}
		if main_rw {
			FirmwareConfig.MainRwPayload = fakePayload
		}
		if main_ro {
			FirmwareConfig.MainRoPayload = fakePayload
		}
		if ec_ro {
			FirmwareConfig.EcRoPayload = fakePayload
		}
		if pd_ro {
			FirmwareConfig.PdRoPayload = fakePayload
		}
		fmt.Printf("FirmwareConfig %#v \n", FirmwareConfig)

		return &api.InstallFirmwareRequest{FirmwareConfig: &FirmwareConfig}
	}
	fakeDutProto := &lab_api.Dut{
		Id: &lab_api.Dut_Id{Value: "dee you tee"},
		DutType: &lab_api.Dut_Chromeos{Chromeos: &lab_api.Dut_ChromeOS{
			DutModel: &lab_api.DutModel{
				BuildTarget: "test_board",
				ModelName:   "test_model",
			},
		}},
	}

	checkStateName := func(st services.ServiceState, expectedStateName string) {
		if st == nil {
			if len(expectedStateName) > 0 {
				t.Fatalf("expected state %v. got: nil state", expectedStateName)
			}
			return
		}
		stateName := st.Name()
		if stateName != expectedStateName {
			t.Fatalf("expected state %v. got: %v", expectedStateName, stateName)
		}
	}

	type TestCase struct {
		// inputs
		main_rw, main_ro, ec_ro, pd_ro bool
		// expected outputs
		updateRw, updateRo     bool
		expectConstructorError bool
	}

	testCases := []TestCase{
		{ /*in*/ false, false, false, false /*out*/, false, false /*err*/, true},
		{ /*in*/ true, false, false, false /*out*/, true, false /*err*/, false},
		{ /*in*/ false, true, false, false /*out*/, false, true /*err*/, false},
		{ /*in*/ false, false, true, true /*out*/, false, true /*err*/, false},
		{ /*in*/ false, true, true, true /*out*/, false, true /*err*/, false},
		{ /*in*/ true, true, true, true /*out*/, true, true /*err*/, false},
		{ /*in*/ true, true, false, true /*out*/, true, true /*err*/, false},
	}

	// Set up the mock.
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	sam := mock_services.NewMockServiceAdapterInterface(ctrl)

	for _, testCase := range testCases {
		// Create FirmwareService.
		ctx := context.Background()
		fws, err := firmwareservice.NewFirmwareServiceFromExistingConnection(
			ctx,
			fakeDutProto,
			sam,
			nil,
			makeRequest(testCase.main_rw, testCase.main_ro, testCase.ec_ro, testCase.pd_ro),
		)
		// Check if init error is expected/got.
		if err != nil {
			if testCase.expectConstructorError {
				continue
			}
			t.Fatalf("failed to create FirmwareService with test case %#v: %v", testCase, err)
		}
		if err == nil && testCase.expectConstructorError {
			t.Fatalf("expected constructor error for test case %#v. got: %v", testCase, err)
		}
		// Check expected states.
		if testCase.updateRo != fws.UpdateRo() {
			t.Fatalf("test case %#v expects updateRo to be %v. got: %v.", testCase, testCase.updateRo, fws.UpdateRo())
		}
		if testCase.updateRw != fws.UpdateRw() {
			t.Fatalf("test case %#v expects updateRw to be %v. got: %v.", testCase, testCase.updateRw, fws.UpdateRw())
		}

		// Start with the first state of the service.
		st := fws.GetFirstState()
		// Confirm state name is Prepare.
		checkStateName(st, firmwareservice.PrepareStateName)

		// Set mock expectations.
		gomock.InOrder(
			sam.EXPECT().RunCmd(gomock.Any(), "mktemp", gomock.Any()).Return("", nil),
			sam.EXPECT().CopyData(gomock.Any(), gomock.Eq(fakeGSPath), gomock.Eq(fakeGSFilename)).Return(nil),
			sam.EXPECT().RunCmd(gomock.Any(), "tar", gomock.Any()).Return(imagesWithinArchive, nil),
		)

		// Execute the state and proceed.
		err = st.Execute(ctx)
		if err != nil {
			t.Fatal(err)
		}
		log.Printf("early state: %v\n", st.Name())
		st = st.Next()
		log.Printf("early state after Next(): %v\n", st.Name())

		if testCase.updateRo {
			// Confirm state name is RO.
			checkStateName(st, firmwareservice.UpdateRoStateName)

			// Set mock expectations.
			expectedFutilityImageArgs := []string{}
			if testCase.main_ro {
				expectedFutilityImageArgs = append(expectedFutilityImageArgs, "--image="+apImageWithinArchive)
				gomock.InOrder(
					sam.EXPECT().RunCmd(gomock.Any(), "cd", gomock.Any()).Return("", nil), // tar
				)
			}
			if testCase.ec_ro {
				expectedFutilityImageArgs = append(expectedFutilityImageArgs, "--ec_image="+ecImageWithinArchive)
				gomock.InOrder(
					sam.EXPECT().RunCmd(gomock.Any(), "cd", gomock.Any()).Return("", nil), // tar
				)
			}
			if testCase.pd_ro {
				expectedFutilityImageArgs = append(expectedFutilityImageArgs, "--pd_image="+pdImageWithinArchive)
				gomock.InOrder(
					sam.EXPECT().RunCmd(gomock.Any(), "cd", gomock.Any()).Return("", nil), // tar
				)
			}
			expectedFutilityArgs := append([]string{"update", "--mode=recovery"}, expectedFutilityImageArgs...)
			expectedFutilityArgs = append(expectedFutilityArgs, "--wp=0")
			gomock.InOrder(
				sam.EXPECT().RunCmd(gomock.Any(), "futility", expectedFutilityArgs).Return("", nil),
			)

			// Execute the state and proceed.
			err := st.Execute(ctx)
			if err != nil {
				t.Fatal(err)
			}
			st = st.Next()
		}

		if testCase.updateRw {
			// Confirm state name is RW.
			checkStateName(st, firmwareservice.UpdateRwStateName)

			// Set mock expectations.
			expectedFutilityArgs := []string{"update", "--mode=recovery", "--image=" + apImageWithinArchive, "--wp=1"}
			gomock.InOrder(
				sam.EXPECT().RunCmd(gomock.Any(), "cd", gomock.Any()).Return("", nil), // tar
				sam.EXPECT().RunCmd(gomock.Any(), "futility", expectedFutilityArgs).Return("", nil),
			)

			// Execute the state and proceed.
			err := st.Execute(ctx)
			if err != nil {
				t.Fatal(err)
			}
			st = st.Next()
		}

		// Confirm state name is postinstall.
		checkStateName(st, firmwareservice.PostInstallStateName)
		// Set mock expectations.
		gomock.InOrder(
			sam.EXPECT().DeleteDirectory(gomock.Any(), "").Return(nil),
			sam.EXPECT().Restart(gomock.Any()).Return(nil),
			sam.EXPECT().RunCmd(gomock.Any(), "true", nil).Return("", nil),
		)
		// Execute the state and proceed.
		err = st.Execute(ctx)
		if err != nil {
			t.Fatal(err)
		}
		st = st.Next()

		// Confirm no states left.
		checkStateName(st, "")
	}
}
