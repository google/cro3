// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crosservice state machine construction and helper
package crosservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/info"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"
	"log"
	"path"
	"regexp"
	"strings"

	conf "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
)

// CrOSService inherits ServiceInterface
type CrOSService struct {
	connection        services.ServiceAdapterInterface
	imagePath         *conf.StoragePath
	overwritePayload  *conf.StoragePath
	preserverStateful bool
	dlcSpecs          []*api.InstallCrosRequest_DLCSpec
}

// NewCrOSService inherits CrOSService
func NewCrOSService(dut *lab_api.Dut, dutClient api.DutServiceClient, req *api.InstallCrosRequest) CrOSService {
	return CrOSService{
		connection:        services.NewServiceAdapter(dut, dutClient, req.GetPreventReboot()),
		imagePath:         req.CrosImagePath,
		overwritePayload:  req.OverwritePayload,
		preserverStateful: req.PreserveStateful,
		dlcSpecs:          req.DlcSpecs,
	}
}

// NewCrOSServiceFromExistingConnection is equivalent to the above constructor,
// but recycles a ServiceAdapter. Generally useful for tests.
func NewCrOSServiceFromExistingConnection(conn services.ServiceAdapterInterface, imagePath *conf.StoragePath, overwritePayload *conf.StoragePath, preserverStateful bool, dlcSpecs []*api.InstallCrosRequest_DLCSpec) CrOSService {
	return CrOSService{
		connection:        conn,
		imagePath:         imagePath,
		overwritePayload:  overwritePayload,
		preserverStateful: preserverStateful,
		dlcSpecs:          dlcSpecs,
	}
}

// GetFirstState returns the first state of this state machine
func (c *CrOSService) GetFirstState() services.ServiceState {
	return CrOSInstallState{
		service: *c,
	}
}

// CleanupOnFailure is called if one of service's states failes to Execute() and
// should clean up the temporary files, and undo the execution, if feasible.
func (c *CrOSService) CleanupOnFailure(states []services.ServiceState, executionErr error) error {
	// TODO: evaluate whether cleanup is needed.
	return nil
}

/*
	Constant Variables
*/

const curlWithRetries = "curl -S -s -v -# -C - --retry 3 --retry-delay 60"

const pipeStatusHandler = `
pipestatus=("${PIPESTATUS[@]}")
if [[ "${pipestatus[0]}" -ne 0 ]]; then
  echo "$(date --rfc-3339=seconds) ERROR: Fetching %[1]s failed." >&2
  exit 1
elif [[ "${pipestatus[1]}" -ne 0 ]]; then
  echo "$(date --rfc-3339=seconds) ERROR: Decompressing %[1]s failed." >&2
  exit 1
elif [[ "${pipestatus[2]}" -ne 0 ]]; then
  echo "$(date --rfc-3339=seconds) ERROR: Writing to %[2]s failed." >&2
  exit 1
fi`

var reBoard = regexp.MustCompile(`CHROMEOS_RELEASE_BOARD=(.*)`)

/*
	The following run specific commands related to CrOS installation.
*/

// CreateProvisionMarker Creates a marker, whose existance signals a failure in provisioning
func (c *CrOSService) CreateProvisionMarker(ctx context.Context) error {
	if _, err := c.connection.RunCmd(ctx, "touch", []string{info.ProvisionMarker}); err != nil {
		return fmt.Errorf("failed to create provisionFailed file, %w", err)
	}
	return nil
}

// GetRoot returns the rootdev outoput for root
func (c *CrOSService) GetRoot(ctx context.Context) (string, error) {
	// Example 1: "/dev/nvme0n1p3"
	// Example 2: "/dev/sda3"
	curRoot, err := c.connection.RunCmd(ctx, "rootdev", []string{"-s"})
	if err != nil {
		return "", fmt.Errorf("failed to get current root, %s", err)
	}
	return strings.TrimSpace(curRoot), nil
}

// GetRootDisk returns the rootdev output for disk
func (c *CrOSService) GetRootDisk(ctx context.Context) (string, error) {
	// Example 1: "/dev/nvme0n1"
	// Example 2: "/dev/sda"
	rootDisk, err := c.connection.RunCmd(ctx, "rootdev", []string{"-s", "-d"})
	if err != nil {
		return "", fmt.Errorf("failed to get root disk, %s", err)
	}
	return strings.TrimSpace(rootDisk), nil
}

// GetRootPartNumber parses the root number for a specific root
func (c *CrOSService) GetRootPartNumber(ctx context.Context, root string) (string, error) {
	// Handle /dev/mmcblk0pX, /dev/sdaX, etc style partitions.
	// Example 1: "3"
	// Example 2: "3"
	match := regexp.MustCompile(`.*([0-9]+)`).FindStringSubmatch(root)
	if match == nil {
		return "", fmt.Errorf("failed to match partition number from %s", root)
	}

	switch match[1] {
	case info.PartitionNumRootA, info.PartitionNumRootB:
		break
	default:
		return "", fmt.Errorf("invalid partition number %s", match[1])
	}

	return match[1], nil
}

// StopSystemDaemon stops system daemons than can interfere with provisioning.
func (c *CrOSService) StopSystemDaemons(ctx context.Context) {
	if _, err := c.connection.RunCmd(ctx, "stop", []string{"ui"}); err != nil {
		log.Printf("Failed to stop UI daemon, %s", err)
	}
	if _, err := c.connection.RunCmd(ctx, "stop", []string{"update-engine"}); err != nil {
		log.Printf("Failed to stop update-engine daemon, %s", err)
	}
}

// ClearDLCArtifacts will clear the verified marks for all DLCs in the inactive slots.
func (c *CrOSService) ClearDLCArtifacts(ctx context.Context, rootPartNum string) error {
	exists, err := c.connection.PathExists(ctx, info.DlcLibDir)
	if err != nil {
		return fmt.Errorf("failed path existance, %s", err)
	}
	if !exists {
		return fmt.Errorf("DLC path does not exist")
	}

	// Stop dlcservice daemon in order to not interfere with clearing inactive verified DLCs.
	if _, err := c.connection.RunCmd(ctx, "stop", []string{"dlcservice"}); err != nil {
		log.Printf("clear DLC artifacts: failed to stop dlcservice daemon, %s", err)
	}
	defer func() {
		if _, err := c.connection.RunCmd(ctx, "start", []string{"dlcservice"}); err != nil {
			log.Printf("clear DLC artifacts: failed to start dlcservice daemon, %s", err)
		}
	}()

	inactiveSlot := info.InactiveDlcMap[rootPartNum]
	if inactiveSlot == "" {
		return fmt.Errorf("invalid root partition number: %s", rootPartNum)
	}
	_, err = c.connection.RunCmd(ctx, "rm", []string{"-f", path.Join(info.DlcCacheDir, "*", "*", string(inactiveSlot), info.DlcVerified)})
	if err != nil {
		return fmt.Errorf("failed remove inactive verified DLCs, %s", err)
	}

	return nil
}

// InstallPartitions  installs the kernel and root images in parallel
func (c *CrOSService) InstallPartitions(ctx context.Context, pi info.PartitionInfo) error {
	if err := c.InstallZippedImage(ctx, "full_dev_part_KERN.bin.gz", pi.InactiveKernel); err != nil {
		return fmt.Errorf("install kernel: %s", err)
	}
	if err := c.InstallZippedImage(ctx, "full_dev_part_ROOT.bin.gz", pi.InactiveRoot); err != nil {
		return fmt.Errorf("install root: %s", err)
	}
	return nil
}

// InstallZippedImage installs a remote zipped image to disk.
func (c *CrOSService) InstallZippedImage(ctx context.Context, remoteImagePath string, outputFile string) error {
	if c.imagePath.HostType == conf.StoragePath_LOCAL || c.imagePath.HostType == conf.StoragePath_HOSTTYPE_UNSPECIFIED {
		return fmt.Errorf("only GS copying is implemented")
	}
	err := c.connection.PipeData(ctx,
		bucketJoin(c.imagePath.GetPath(), remoteImagePath),
		fmt.Sprintf("gzip -d | %s %s", fmt.Sprintf("dd of=%s obs=2M", outputFile), fmt.Sprintf(pipeStatusHandler, c.imagePath.GetPath(), outputFile)),
	)
	if err != nil {
		return fmt.Errorf("failed to install image, %w", err)
	}
	return nil
}

// PostInstall mounts and runs post installation items.
func (c *CrOSService) PostInstall(ctx context.Context, inactiveRoot string) error {
	tmpMnt, err := c.connection.RunCmd(ctx, "mktemp", []string{"-d"})
	if err != nil {
		return fmt.Errorf("failed to create temporary directory, %s", err)
	}
	tmpMnt = strings.TrimSpace(tmpMnt)
	if _, err := c.connection.RunCmd(ctx, "mount", []string{"-o", "ro", inactiveRoot, tmpMnt}); err != nil {
		return fmt.Errorf("failed to mount inactive root, %s", err)
	}
	if _, err := c.connection.RunCmd(ctx, fmt.Sprintf("%s/postinst", tmpMnt), []string{inactiveRoot}); err != nil {
		return fmt.Errorf("failed to postinst from inactive root, %s", err)
	}
	if _, err := c.connection.RunCmd(ctx, "umount", []string{tmpMnt}); err != nil {
		return fmt.Errorf("failed to umount temporary directory, %s", err)
	}
	if _, err := c.connection.RunCmd(ctx, "rmdir", []string{tmpMnt}); err != nil {
		return fmt.Errorf("failed to remove temporary directory, %s", err)
	}
	return nil
}

// ClearTPM runs crosssystem clear tpm request
func (c *CrOSService) ClearTPM(ctx context.Context) error {
	_, err := c.connection.RunCmd(ctx, "crossystem", []string{"clear_tpm_owner_request=1"})
	return err
}

// RevertStatefulInstall literally reverses a stateful installation
func (c *CrOSService) RevertStatefulInstall(ctx context.Context) {
	varNewPath := path.Join(info.StatefulPath, "var_new")
	devImageNewPath := path.Join(info.StatefulPath, "dev_image_new")
	_, err := c.connection.RunCmd(ctx, "rm", []string{"-rf", varNewPath, devImageNewPath, info.UpdateStatefulFilePath})
	if err != nil {
		log.Printf("revert stateful install: failed to revert stateful installation, %s", err)
	}
}

// RevertPostInstall literally reverses a PostInstall
func (c *CrOSService) RevertPostInstall(ctx context.Context, activeRoot string) {
	if _, err := c.connection.RunCmd(ctx, "/postinst", []string{activeRoot, "2>&1"}); err != nil {
		log.Printf("revert post install: failed to revert postinst, %s", err)
	}
}

// RevertProvisionOS literally reverts a full OS provisioning
func (c *CrOSService) RevertProvisionOS(ctx context.Context, activeRoot string) {
	c.RevertStatefulInstall(ctx)
	c.RevertPostInstall(ctx, activeRoot)
}

// WipeStateful removes all things relevant to a stateful install
func (c *CrOSService) WipeStateful(ctx context.Context) error {
	if _, err := c.connection.RunCmd(ctx, "echo", []string{"'fast keepimg'", ">", "/mnt/stateful_partition/factory_install_reset"}); err != nil {
		return fmt.Errorf("failed to to write to factory reset file, %s", err)
	}
	return nil
}

// ProvisionStateful runs a stateful install, reverting if it fails.
func (c *CrOSService) ProvisionStateful(ctx context.Context) error {
	c.StopSystemDaemons(ctx)

	if err := c.InstallStateful(ctx); err != nil {
		c.RevertStatefulInstall(ctx)
		return fmt.Errorf("failed to install stateful partition, %s", err)
	}
	return nil
}

// InstallStateful updates the stateful partition on disk (finalized after a reboot).
func (c *CrOSService) InstallStateful(ctx context.Context) error {
	if c.imagePath.HostType == conf.StoragePath_LOCAL || c.imagePath.HostType == conf.StoragePath_HOSTTYPE_UNSPECIFIED {
		return fmt.Errorf("only GS copying is implemented")
	}

	if _, err := c.connection.RunCmd(ctx, "rm", []string{
		"-rf", info.UpdateStatefulFilePath, path.Join(info.StatefulPath, "var_new"), path.Join(info.StatefulPath, "dev_image_new"),
	}); err != nil {
		return err
	}

	if err := c.connection.PipeData(ctx,
		bucketJoin(c.imagePath.GetPath(), "stateful.tgz"),
		fmt.Sprintf("tar --ignore-command-error --overwrite --directory=%s -xzf -", info.StatefulPath)); err != nil {
		return err
	}

	_, err := c.connection.RunCmd(ctx, "echo", []string{
		"-n", "clobber", ">", info.UpdateStatefulFilePath,
	})

	return err
}

// OverwiteInstall will over write the existing install
func (c *CrOSService) OverwiteInstall(ctx context.Context) error {
	if c.overwritePayload == nil {
		log.Printf("skipping overwrite install, because none was specified.")
		return nil
	}
	if c.overwritePayload.HostType == conf.StoragePath_LOCAL || c.overwritePayload.HostType == conf.StoragePath_HOSTTYPE_UNSPECIFIED {
		return fmt.Errorf("only GS copying is implemented")
	}
	err := c.connection.PipeData(ctx, c.overwritePayload.GetPath(), "tar xf - -C /")
	if err != nil {
		return fmt.Errorf("failed to download and untar file, %s", err)
	}
	return nil
}

// StopDLCService stops a DLC service
func (c *CrOSService) StopDLCService(ctx context.Context) {
	if _, err := c.connection.RunCmd(ctx, "stop", []string{"dlcservice"}); err != nil {
		log.Printf("failed to stop dlcservice daemon, %s", err)
	}
}

// StartDLCService starts a DLC service
func (c *CrOSService) StartDLCService(ctx context.Context) {
	if _, err := c.connection.RunCmd(ctx, "start", []string{"dlcservice"}); err != nil {
		log.Printf("failed to start dlcservice daemon, %s", err)
	}
}

// InstallDLC installs all relevant DLCs
func (c *CrOSService) InstallDLC(ctx context.Context, spec *api.InstallCrosRequest_DLCSpec, slot string) error {
	dlcID := spec.GetId()
	dlcOutputDir := path.Join(info.DlcCacheDir, dlcID, info.DlcPackage)
	verified, err := c.IsDLCVerified(ctx, spec.GetId(), slot)
	if err != nil {
		return fmt.Errorf("failed is DLC verified check, %s", err)
	}

	// Skip installing the DLC if already verified.
	if verified {
		log.Printf("provision DLC %s skipped as already verified", dlcID)
		return nil
	}

	if c.imagePath.HostType == conf.StoragePath_LOCAL || c.imagePath.HostType == conf.StoragePath_HOSTTYPE_UNSPECIFIED {
		return fmt.Errorf("only GS copying is implemented")
	}
	dlcURL := path.Join(c.imagePath.GetPath(), "dlc", dlcID, info.DlcPackage, info.DlcImage)

	dlcOutputSlotDir := path.Join(dlcOutputDir, string(slot))
	dlcOutputImage := path.Join(dlcOutputSlotDir, info.DlcImage)
	if err := c.connection.CreateDirectories(ctx, []string{dlcOutputSlotDir}); err != nil {
		return fmt.Errorf("failed to create DLC directories %s, %s", dlcID, err)
	}
	if err := c.connection.CopyData(ctx, dlcURL, dlcOutputImage); err != nil {
		return fmt.Errorf("failed to download DLCs, %s", err)
	}

	return nil
}

// IsDLCVerified checks if the desired DLC already exists within the system
func (c *CrOSService) IsDLCVerified(ctx context.Context, dlcID, slot string) (bool, error) {
	verified, err := c.connection.PathExists(ctx, path.Join(info.DlcLibDir, dlcID, slot, info.DlcVerified))
	if err != nil {
		return false, fmt.Errorf("failed to check if DLC %s is verified, %s", dlcID, err)
	}
	return verified, nil
}

// IsMiniOSPartitionSupported determines whether the device has the partitions
func (c *CrOSService) IsMiniOSPartitionSupported(ctx context.Context, rootDisk string, rootPart string) (bool, error) {
	guidPartition, err := c.connection.RunCmd(ctx, "cgpt", []string{"show", "-t", rootDisk, rootPart})
	if err != nil {
		return false, fmt.Errorf("failed to get partition type, %s", err)
	}

	return strings.TrimSpace(guidPartition) != info.MiniOSUnsupportedGUIDPartition, nil
}

// InstallMiniOS downloads and installs the minios images
func (c *CrOSService) InstallMiniOS(ctx context.Context, pi info.PartitionInfo) error {
	if err := c.InstallZippedImage(ctx, "full_dev_part_MINIOS.bin.gz", pi.MiniOSA); err != nil {
		return fmt.Errorf("install MiniOS A: %s", err)
	}
	if err := c.InstallZippedImage(ctx, "full_dev_part_MINIOS.bin.gz", pi.MiniOSB); err != nil {
		return fmt.Errorf("install MiniOS B: %s", err)
	}
	return nil
}

// getBoard returns the name of the current board
func (c *CrOSService) getBoard(ctx context.Context) (string, error) {
	lsbRelease, err := c.connection.RunCmd(ctx, "cat", []string{"/etc/lsb-release"})
	if err != nil {
		return "", fmt.Errorf("failed to read lsb-release")
	}

	match := reBoard.FindStringSubmatch(lsbRelease)
	if match == nil {
		return "", fmt.Errorf("no match found in lsb-release for %s", reBoard.String())
	}
	return match[1], nil
}

// CanClearTPM determines whether the current board can clear TPM
func (c *CrOSService) CanClearTPM(ctx context.Context) bool {
	board, err := c.getBoard(ctx)
	if err != nil {
		log.Printf("could not determine board, %s", err)
		return false
	}
	return !strings.HasPrefix(board, "raven")
}

// CorrectDLCPermissions changes the permission and ownership of DLC cache to
// the correct one. As part of the transition to using tmpfiles.d, dlcservice
// paths must have correct permissions/owners set. Simply starting the
// dlcservice daemon will not fix this due to security concerns.
func (c *CrOSService) CorrectDLCPermissions(ctx context.Context) error {
	if _, err := c.connection.RunCmd(ctx, "chown", []string{"-R", "dlcservice:dlcservice", info.DlcCacheDir}); err != nil {
		return fmt.Errorf("unable to set owner for DLC cache (%s), %s", info.DlcCacheDir, err)
	}

	if _, err := c.connection.RunCmd(ctx, "chmod", []string{"-R", "0755", info.DlcCacheDir}); err != nil {
		return fmt.Errorf("unable to set permissions for DLC cache (%s), %s", info.DlcCacheDir, err)
	}

	return nil
}

func bucketJoin(bucket string, append string) string {
	if strings.HasPrefix(bucket, "gs://") {
		bucket = bucket[5:]
	}
	return fmt.Sprintf("gs://%s", path.Join(bucket, append))
}
