// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package firmwareservice

import (
	"context"
	"errors"
	"fmt"
	"log"
	"strings"
	"time"

	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"chromiumos/test/provision/lib/servo_lib"
	"chromiumos/test/provision/lib/servoadapter"

	conf "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
)

// FirmwareService inherits ServiceInterface
type FirmwareService struct {
	// In case of flashing over SSH, |connection| connects to the DUT.
	// In case of flashing over Servo, |connection| connects to the ServoHost.
	connection services.ServiceAdapterInterface

	mainRwPath *conf.StoragePath

	mainRoPath *conf.StoragePath
	ecRoPath   *conf.StoragePath
	pdRoPath   *conf.StoragePath

	board, model string

	force bool

	ecChip string

	// imagesMetadata is a map from gspath -> ImageArchiveMetadata.
	// Allows to avoid redownloading/reprocessing archives.
	imagesMetadata map[string]ImageArchiveMetadata

	useServo bool
	// servoConfig provides dut-controls and programmer argument for flashing
	servoConfig *servo_lib.ServoConfig
	// wrapper around servoClient connection with extra servod-related functions
	servoConnection servoadapter.ServoHostInterface
	servoPort       int
}

func NewFirmwareService(ctx context.Context, dut *lab_api.Dut, dutClient api.DutServiceClient, servoClient api.ServodServiceClient, req *api.InstallFirmwareRequest) (*FirmwareService, error) {
	connection := services.NewServiceAdapter(dut, dutClient, false /*noReboot*/)
	return NewFirmwareServiceFromExistingConnection(ctx, dut, connection, servoClient, req)
}

// NewFirmwareServiceFromExistingConnection is equivalent to the above constructor,
// but recycles a ServiceAdapter. Generally useful for tests.
func NewFirmwareServiceFromExistingConnection(ctx context.Context, dut *lab_api.Dut, connection services.ServiceAdapterInterface, servoClient api.ServodServiceClient, req *api.InstallFirmwareRequest) (*FirmwareService, error) {
	if req.FirmwareConfig == nil {
		return nil, errors.New("request.FirmwareConfig is nil")
	}

	// Firmware may be updated in write-protected mode, where only 'rw' regions
	// would be update, or write-protection may be disabled (dangerous) in order
	// to update 'ro' regions.
	//
	// The only 'rw' firmware is the main one, aka AP firmware, which also syncs
	// EC 'rw'. It will be flashed with write protection turned on.
	mainRwPath := req.FirmwareConfig.MainRwPayload.GetFirmwareImagePath()

	// Read-only firmware images include AP, EC, and PD firmware, and will be
	// flashed with write protection turned off.
	mainRoPath := req.FirmwareConfig.MainRoPayload.GetFirmwareImagePath()
	ecRoPath := req.FirmwareConfig.EcRoPayload.GetFirmwareImagePath()
	pdRoPath := req.FirmwareConfig.PdRoPayload.GetFirmwareImagePath()

	imagesMetadata := make(map[string]ImageArchiveMetadata)

	board := dut.GetChromeos().GetDutModel().GetBuildTarget()
	if len(board) == 0 {
		return nil, errors.New("\"board\" field in Dut proto is required")
	}
	model := dut.GetChromeos().GetDutModel().GetModelName()
	if len(model) == 0 {
		return nil, errors.New("\"model\" field in Dut proto is required")
	}

	force := req.GetForce()
	useServo := req.GetUseServo()

	var servoConfig *servo_lib.ServoConfig
	var servoConnection servoadapter.ServoHostInterface
	var ecChip string
	var servoPort int

	if useServo {
		if servoClient == nil {
			return nil, fmt.Errorf("servo use is requested, but servo client not provided")
		}

		// Note: dut.GetChromeos().Servo.ServodAddress.Port is the port of cros-servod service,
		// we seem to be missing port of servod itself.
		if servoPort == 0 {
			servoPort = 9999
		}

		servoConnection = servoadapter.NewServoHostAdapterFromExecCmder(board, model, servoPort, servoClient)

		// Ask servod for servo_type. This implicitly checks if servod is running
		// and servo connection is working.
		servoTypeStr, err := servoConnection.GetVariable(ctx, "servo_type")
		if err != nil {
			return nil, fmt.Errorf("failed to get servo_type: %w. "+
				"Is servod running on port %v and connected to the DUT?",
				err, servoPort)
		}

		// ask servod for serial number of the connected DUT.
		servoType := servo_lib.NewServoType(servoTypeStr)

		if servoType.IsMultipleServos() {
			// Handle dual servo.
			// We need CCD if ec_ro is set, otherwise, servo_micro will be faster.
			preferCCD := false
			if req.FirmwareConfig.EcRoPayload.GetFirmwareImagePath() != nil {
				preferCCD = true
			}
			servoSubtypeStr := servoType.PickServoSubtype(preferCCD)
			servoType = servo_lib.NewServoType(servoSubtypeStr)
		}

		serial, err := servoConnection.GetVariable(ctx, servoType.GetSerialNumberOption())
		if err != nil {
			return nil, err
		}

		// finally, get the correct config
		servoConfig, err = servo_lib.GetServoConfig(board, serial, servoType)
		if err != nil {
			return nil, err
		}

		ecChip, err = servoConnection.GetVariable(ctx, "ec_chip")
		if err != nil {
			return nil, err
		}
	}

	fws := FirmwareService{
		connection,
		mainRwPath,
		mainRoPath,
		ecRoPath,
		pdRoPath,
		board,
		model,
		force,
		ecChip,
		imagesMetadata,
		useServo,
		servoConfig,
		servoConnection,
		servoPort,
	}

	fws.PrintRequestInfo()

	if !fws.UpdateRo() && !fws.UpdateRw() {
		return nil, errors.New("request.FirmwareConfig: no paths to images specified")
	}

	return &fws, nil
}

func (fws *FirmwareService) PrintRequestInfo() {
	informationString := "provisioning "

	images := []string{}
	if fws.mainRwPath != nil {
		images = append(images, "AP(RW)")
	}
	if fws.mainRoPath != nil {
		images = append(images, "AP(RO)")
	}
	if fws.ecRoPath != nil {
		images = append(images, "EC(RO)")
	}
	if fws.pdRoPath != nil {
		images = append(images, "PD(RO)")
	}
	informationString += strings.Join(images, " and ") + " firmware"

	flashMode := "SSH"
	if fws.useServo {
		flashMode = fmt.Sprintf("Servo %s", (fws.servoConfig.ServoType))
	}
	informationString += " over " + flashMode + ". "

	informationString += "Board: " + fws.board + ". "

	informationString += "Model: " + fws.model + ". "

	informationString += fmt.Sprintf("Force: %v.", fws.force)

	log.Println("[FW Provisioning]", informationString)
}

func (fws *FirmwareService) UpdateRw() bool {
	return fws.mainRwPath != nil
}

func (fws *FirmwareService) UpdateRo() bool {
	return (fws.mainRoPath != nil) || (fws.ecRoPath != nil) || (fws.pdRoPath != nil)
}

// GetBoard returns board of the DUT to provision. Returns empty string if board is not known.
func (fws *FirmwareService) GetBoard() string {
	return fws.board
}

// RestartDut restarts the DUT using one of the available mechanisms.
// Preferred restart method is to send "power_state:reset" command to servod.
// If servod restarting failed/not available in the environment,
// then this function will try to SSH to the DUT and run `restart`,
// if |requireServoReset| is false. If |requireServoReset| is True, restart over
// SSH will not be attempted, and the function will return an error.
func (fws *FirmwareService) RestartDut(ctx context.Context, requireServoReset bool) error {
	waitForReconnect := func(conn services.ServiceAdapterInterface) error {
		// Attempts to run `true` on the DUT over SSH until |reconnectRetries| attempts.
		const reconnectRetries = 10
		const reconnectAttemptWait = 10 * time.Second
		const reconnectFailPause = 10 * time.Second
		var restartErr error
		for i := 0; i < reconnectRetries; i++ {
			reconnectCtx, reconnCancel := context.WithTimeout(ctx, reconnectAttemptWait)
			defer reconnCancel()
			_, restartErr = conn.RunCmd(reconnectCtx, "true", nil)
			if restartErr == nil {
				log.Println("[FW Provisioning: Restart DUT] reestablished connection to the DUT after restart.")
				return nil
			}
			time.Sleep(reconnectFailPause)
		}
		log.Printf("[FW Provisioning: Restart DUT] timed out waiting for DUT to restart: %v\n", restartErr)
		return restartErr
	}

	if requireServoReset && fws.servoConnection == nil {
		return errors.New("servo restart is required but servo connection not available")
	}
	// over Servo first
	if fws.servoConnection != nil {
		log.Printf("[FW Provisioning: Restart DUT] restarting DUT with \"dut-control power_state:reset\" over servo.\n")
		servoRestartErr := fws.servoConnection.RunDutControl(ctx, []string{"power_state:reset"})
		if servoRestartErr == nil {
			if fws.connection != nil {
				// If SSH connection to DUT was available, wait until it's back up again.
				return waitForReconnect(fws.connection)
			} else {
				waitDuration := 30 * time.Second
				log.Printf("[FW Provisioning: Restart DUT] waiting for %v for DUT to finish rebooting.\n", waitDuration.String())
				time.Sleep(waitDuration)
				powerState, getPowerStateErr := fws.servoConnection.GetVariable(ctx, "ec_system_powerstate")
				if getPowerStateErr != nil {
					log.Printf("[FW Provisioning: Restart DUT] failed to get power state after reboot: %v\n", getPowerStateErr)
				} else {
					log.Printf("[FW Provisioning: Restart DUT] DUT power state after reboot: %v\n", powerState)
				}
				return getPowerStateErr
			}
		}
		log.Printf("[FW Provisioning: Restart DUT] failed to restart DUT via Servo: %v.\n", servoRestartErr)
		if requireServoReset {
			return servoRestartErr
		}
	}

	// over SSH if allowed by |requireServoReset|
	if fws.connection != nil {
		log.Printf("[FW Provisioning: Restart DUT] restarting DUT over SSH.")
		fws.connection.Restart(ctx)
		return waitForReconnect(fws.connection)
	}
	return errors.New("failed to restart: no SSH connection to the DUT")
}

// GetModel returns model of the DUT to provision. Returns empty string if model is not known.
func (fws *FirmwareService) GetModel() string {
	return fws.model
}

// GetFirstState returns the first state of this state machine
func (fws *FirmwareService) GetFirstState() services.ServiceState {
	return FirmwarePrepareState{
		service: *fws,
	}
}

// CleanupOnFailure is called if one of service's states failes to Execute() and
// currenly cleans up the temporary files.
func (fws *FirmwareService) CleanupOnFailure(states []services.ServiceState, executionErr error) error {
	return fws.deleteArchiveDirectories()
}

func (fws *FirmwareService) deleteArchiveDirectories() error {
	var cleanedDevice services.ServiceAdapterInterface
	if fws.useServo {
		// If servo is used, the files will be located on the ServoHost.
		cleanedDevice = fws.servoConnection
	} else {
		// If SSH is used, the files will be located on the DUT in /tmp/
		// It's not strictly necessary to delete them before reboot.
		cleanedDevice = fws.connection
	}

	var allErrors []string
	for _, imgMetadata := range fws.imagesMetadata {
		err := cleanedDevice.DeleteDirectory(context.Background(), imgMetadata.archiveDir)
		if err != nil {
			allErrors = append(allErrors, fmt.Sprintf("failed to delete %v: %v", imgMetadata.archiveDir, err))
		}
	}

	if len(allErrors) > 0 {
		return errors.New(strings.Join(allErrors, ". "))
	}

	return nil
}

// FlashWithFutility flashes the DUT using "futility" tool.
// futility will be run with "--mode=recovery".
// if |rwOnly| is true, futility will flash only RW regions.
// if |rwOnly| is false, futility will flash both RW and RO regions.
// futilityArgs must include argument(s) that provide path(s) to the images.
//
// If flashing over ssh, simply calls runFutility().
// If flashing over servo, also runs pre- and post-flashing dut-controls.
func (fws FirmwareService) FlashWithFutility(ctx context.Context, rwOnly bool, futilityImageArgs []string) error {
	if fws.useServo {
		return fws.servoFlash(ctx, rwOnly, futilityImageArgs)
	} else {
		return fws.sshFlash(ctx, rwOnly, futilityImageArgs)
	}
}

func (fws FirmwareService) sshFlash(ctx context.Context, rwOnly bool, futilityImageArgs []string) error {
	return fws.runFutility(ctx, rwOnly, futilityImageArgs)
}

func (fws FirmwareService) servoFlash(ctx context.Context, rwOnly bool, futilityImageArgs []string) error {
	dutOnErr := fws.servoConnection.RunAllDutControls(ctx, fws.servoConfig.DutOn)
	if dutOnErr != nil {
		return fmt.Errorf("failed to run pre-flashing dut-controls: %w", dutOnErr)
	}

	flashErr := fws.runFutility(ctx, rwOnly, futilityImageArgs)

	// Attempt to run post-flashing dut-controls regardless of flashErr.
	dutOffErr := fws.servoConnection.RunAllDutControls(ctx, fws.servoConfig.DutOff)
	if flashErr != nil {
		return flashErr
	}
	if dutOffErr != nil {
		return fmt.Errorf("failed to run post-flashing dut-controls: %w", dutOffErr)
	}
	return nil
}

func (fws FirmwareService) runFutility(ctx context.Context, rwOnly bool, futilityImageArgs []string) error {
	if len(futilityImageArgs) == 0 {
		return fmt.Errorf("unable to flash: no futility Image args provided")
	}

	futilityArgs := futilityImageArgs
	futilityArgs = append([]string{"update", "--mode=recovery"}, futilityArgs...)

	if rwOnly {
		futilityArgs = append(futilityArgs, "--wp=1")
	} else {
		futilityArgs = append(futilityArgs, "--wp=0")
	}

	if fws.force {
		futilityArgs = append(futilityArgs, "--force")
	}

	if fws.useServo {
		futilityArgs = append(futilityArgs, "-p", fws.servoConfig.Programmer)
		futilityArgs = append(futilityArgs, fws.servoConfig.ExtraArgs...)
		// TODO(sfrolov): extra args from fw-config.json
	}

	connection := fws.GetConnectionToFlashingDevice()
	if _, err := connection.RunCmd(ctx, "futility", futilityArgs); err != nil {
		return err
	}
	return nil
}

// GetConnectionToFlashingDevice returns connection to the device that stores the
// firmware image and runs futility.
// Returns connection to ServoHost if fws.useServo, connection to DUT otherwise.
func (fws FirmwareService) GetConnectionToFlashingDevice() services.ServiceAdapterInterface {
	if fws.useServo {
		return fws.servoConnection
	} else {
		return fws.connection
	}
}

// ProvisionWithFlashEC flashes EC image using flash_ec script.
func (fws FirmwareService) ProvisionWithFlashEC(ctx context.Context, ecImage, flashECScriptPath string) error {
	customBitbangRate := ""
	if fws.ecChip == "stm32" {
		customBitbangRate = "--bitbang_rate=57600"
	}
	flashCmdArgs := fmt.Sprintf("--ro --chip=%s --board=%s --image=%s --port=%v %s --verify --verbose",
		fws.ecChip, fws.model, ecImage, fws.servoPort, customBitbangRate)
	output, err := fws.GetConnectionToFlashingDevice().RunCmd(ctx, flashECScriptPath, strings.Split(flashCmdArgs, " "))
	if err != nil {
		log.Println(output)
		return err
	}
	return nil
}
