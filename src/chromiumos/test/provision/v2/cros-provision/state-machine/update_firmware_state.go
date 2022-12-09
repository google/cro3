// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Third step of CrOSInstall State Machine. Responsible for update firmware
package state_machine

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"
	"chromiumos/test/provision/v2/cros-provision/state-machine/commands"
	"context"
	"fmt"
	"log"
	"time"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/protobuf/types/known/anypb"
)

type CrosUpdateFirmwareState struct {
	service *service.CrOSService
}

func (s CrosUpdateFirmwareState) Execute(ctx context.Context, log *log.Logger) (*anypb.Any, api.InstallResponse_Status, error) {
	if !s.service.UpdateFirmware {
		log.Printf("State: Skip CrosUpdateFirmwareState by request")
		return nil, api.InstallResponse_STATUS_OK, nil
	}
	// Some type of build(e.g. public build) doesn't have built-in firmware updater, so skip the firmware update in this case.
	checkUpdaterComm := commands.NewCheckFirmwareUpdaterCommand(ctx, s.service)
	if err := checkUpdaterComm.Execute(log); err != nil {
		return nil, checkUpdaterComm.GetStatus(), fmt.Errorf("%s, %s", checkUpdaterComm.GetErrorMessage(), err)
	}
	if !checkUpdaterComm.UpdaterExist {
		log.Printf("State: Skip CrosUpdateFirmwareState as firmware updater does not exist on the build")
		return nil, api.InstallResponse_STATUS_OK, nil
	}

	log.Printf("State: Execute CrosUpdateFirmwareState")

	comms := []common_utils.CommandInterface{
		commands.NewWaitForDutToStabilizeCommand(ctx, s.service),
		commands.NewRunFirmwareUpdaterCommand(ctx, s.service),
	}
	checkFirmwareSlotComm := commands.NewCheckFirmwareSlotCommand(ctx, s.service)
	comms = append(comms, checkFirmwareSlotComm)

	for i, comm := range comms {
		err := comm.Execute(log)
		if err != nil {
			for ; i >= 0; i-- {
				log.Printf("CrosUpdateFirmwareState REVERT CALLED")
				if innerErr := comm.Revert(); innerErr != nil {
					return nil, comm.GetStatus(), fmt.Errorf("failure while reverting, %s: %s", err, innerErr)
				}
			}
			return nil, comm.GetStatus(), fmt.Errorf("%s, %s", comm.GetErrorMessage(), err)
		}
	}
	// Reboot if firmware slot changed.
	if checkFirmwareSlotComm.RebootRequired {
		// Post firmware update reboot could take longer time, so give it 300 seconds timeout here.
		rebootComm := commands.NewRebootWithTimeoutCommand(300*time.Second, ctx, s.service)
		if err := rebootComm.Execute(log); err != nil {
			return nil, rebootComm.GetStatus(), fmt.Errorf("%s, %s", rebootComm.GetErrorMessage(), err)
		}
	} else {
		log.Printf("no firmware slot change detected, skip post firmware update reboot.")
	}
	verifyFirmwareComm := commands.NewVerifyFirmwareCommand(ctx, s.service)
	if err := verifyFirmwareComm.Execute(log); err != nil {
		return nil, verifyFirmwareComm.GetStatus(), fmt.Errorf("%s, %s", verifyFirmwareComm.GetErrorMessage(), err)
	}

	log.Printf("State: CrosUpdateFirmwareState Completed")

	return nil, api.InstallResponse_STATUS_OK, nil
}

func (s CrosUpdateFirmwareState) Next() common_utils.ServiceState {
	return CrOSPostInstallState{
		service: s.service,
	}
}

func (s CrosUpdateFirmwareState) Name() string {
	return "CrOS Update Firmware"
}
