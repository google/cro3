// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// FirmwareInstall state machine construction and helper

package firmwareservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"errors"
	"fmt"
	"path"

	conf "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
)

const FirmwarePathTmp = "/tmp/fw-provisioning-service/"

// FirmwareService inherits ServiceInterface
type FirmwareService struct {
	connection services.ServiceAdapterInterface

	mainRwPath *conf.StoragePath

	mainRoPath *conf.StoragePath
	ecRoPath   *conf.StoragePath
	pdRoPath   *conf.StoragePath
}

const CurlWithRetriesArgsFW = "-S -s -v -# -C - --retry 3 --retry-delay 60"

func NewFirmwareService(dut *lab_api.Dut, dutClient api.DutServiceClient, req *api.InstallFirmwareRequest) (*FirmwareService, error) {
	fws, err := newConnectionlessFirmwareService(req)
	if err != nil {
		return nil, err
	}

	fws.connection = services.NewServiceAdapter(dut, dutClient, false /*noReboot*/)
	if err := fws.connection.CreateDirectories(context.Background(), []string{FirmwarePathTmp}); err != nil {
		return nil, fmt.Errorf("failed to create folder %v: %w", FirmwarePathTmp, err)
	}

	return fws, nil
}

// NewFirmwareServiceFromExistingConnection is equivalent to the above constructor,
// but recycles a ServiceAdapter. Generally useful for tests.
func NewFirmwareServiceFromExistingConnection(connection services.ServiceAdapterInterface, req *api.InstallFirmwareRequest) (*FirmwareService, error) {
	fws, err := newConnectionlessFirmwareService(req)
	if err != nil {
		return nil, err
	}

	fws.connection = connection
	if err := fws.connection.CreateDirectories(context.Background(), []string{FirmwarePathTmp}); err != nil {
		return nil, fmt.Errorf("failed to create folder %v: %w", FirmwarePathTmp, err)
	}

	return fws, nil
}

// newConnectionlessFirmwareService is a contructor helper function that builds
// FirmwareService given a request, but leaves connection nil.
func newConnectionlessFirmwareService(req *api.InstallFirmwareRequest) (*FirmwareService, error) {
	if req.FirmwareConfig == nil {
		return nil, errors.New("request.FirmwareConfig is nil")
	}

	// Firmware may be updated in write-protected mode, where only 'rw' regions
	// would be update, or write-protection may be disabled (dangerous) in order
	// to update 'ro' regions.

	// The only 'rw' firmware is the main one, aka AP firmware.
	// Do it with write protection.
	mainRwPath := req.FirmwareConfig.MainRwPayload.GetFirmwareImagePath()

	// We may need to update 'ro' AP, EC, and PD(non-existent by now?) firmware.
	// Disable write protection.
	mainRoPath := req.FirmwareConfig.MainRoPayload.GetFirmwareImagePath()
	ecRoPath := req.FirmwareConfig.EcRoPayload.GetFirmwareImagePath()
	pdRoPath := req.FirmwareConfig.PdRoPayload.GetFirmwareImagePath()

	connection := services.ServiceAdapterInterface(nil)
	fws := FirmwareService{
		connection,
		mainRwPath,
		mainRoPath,
		ecRoPath,
		pdRoPath,
	}

	if !fws.UpdateRo() && !fws.UpdateRw() {
		return nil, errors.New("request.FirmwareConfig: no paths to images specified")
	}

	return &fws, nil
}

func (fws *FirmwareService) UpdateRw() bool {
	return fws.mainRwPath != nil
}
func (fws *FirmwareService) UpdateRo() bool {
	return (fws.mainRoPath != nil) || (fws.ecRoPath != nil) || (fws.pdRoPath != nil)
}

// GetFirstState returns the first state of this state machine
func (fws *FirmwareService) GetFirstState() services.ServiceState {
	if fws.UpdateRw() {
		return FirmwareUpdateRwState{
			service: *fws,
		}
	} else if fws.UpdateRo() {
		return FirmwareUpdateRoState{
			service: *fws,
		}
	}
	return nil
}

// CleanupOnFailure is called if one of service's states failes to Execute() and
// should clean up the temporary files, and undo the execution, if feasible.
func (fws *FirmwareService) CleanupOnFailure(states []services.ServiceState, executionErr error) error {
	// TODO(sfrolov): implement cleanup.
	return nil
}

// CopyImageToDUT copies the desired image to the DUT, passing through the caching layer.
func (fws *FirmwareService) CopyImageToDUT(ctx context.Context, remotePath *conf.StoragePath, localFilename string) error {
	if remotePath.HostType == conf.StoragePath_LOCAL || remotePath.HostType == conf.StoragePath_HOSTTYPE_UNSPECIFIED {
		return fmt.Errorf("only GS copying is implemented")
	}
	if err := fws.connection.CopyData(ctx, remotePath.GetPath(), fws.GetImagePath(localFilename)); err != nil {
		return fmt.Errorf("failed to cache %v: %w", remotePath.GetPath(), err)
	}

	return nil
}

// ExecuteWPFutility executes "futility" flashing utility with write protection.
// futility will be run with "--mode=autoupdate" and "--wp=1".
// futilityImageArg must include an argument to futility that provides a path
// to the AP image to be flashed.
func (fws FirmwareService) ExecuteWPFutility(ctx context.Context, futilityImageArg string) error {
	if len(futilityImageArg) == 0 {
		return fmt.Errorf("unable to flash: no futility Image args provided")
	}
	futilityArgs := []string{"update", "--mode=autoupdate", "--wp=1"}

	futilityArgs = append(futilityArgs, futilityImageArg)

	if _, err := fws.connection.RunCmd(ctx, "futility", futilityArgs); err != nil {
		return err
	}
	return nil
}

// ExecuteFutility executes "futility" flashing utility without write protection
// futility will be run with "--mode=recovery" and "--wp=0"
// futilityImageArgs must include argument(s) to futility that provide path(s)
// to the AP/EC/PD images to be flashed.
func (fws FirmwareService) ExecuteFutility(ctx context.Context, futilityImageArgs []string) error {
	if len(futilityImageArgs) == 0 {
		return fmt.Errorf("unable to flash: no futility Image args provided")
	}
	futilityArgs := []string{"update", "--mode=recovery", "--wp=0"}

	futilityArgs = append(futilityArgs, futilityImageArgs...)

	if _, err := fws.connection.RunCmd(ctx, "futility", futilityArgs); err != nil {
		return err
	}
	return nil
}

// GetImagePath returns joined path of directory with firmware and provided filename.
func (fws *FirmwareService) GetImagePath(filename string) string {
	return path.Join(FirmwarePathTmp, filename)
}
