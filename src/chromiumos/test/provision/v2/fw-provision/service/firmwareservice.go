// Copyright 2022 The ChromiumOS Authors.
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

	"chromiumos/test/provision/lib/servo_lib"
	"chromiumos/test/provision/lib/servoadapter"
	common_utils "chromiumos/test/provision/v2/common-utils"

	conf "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
)

// FirmwareService implements ServiceInterface
type FirmwareService struct {
	// In case of flashing over SSH, |connection| connects to the DUT.
	// In case of flashing over Servo, |connection| connects to the ServoHost.
	connection common_utils.ServiceAdapterInterface

	useSimpleRequest bool
	// DetailedRequest fields
	mainRwPath *conf.StoragePath
	mainRoPath *conf.StoragePath
	ecRoPath   *conf.StoragePath
	pdRoPath   *conf.StoragePath
	// SimpleRequest fields
	simpleImagePath *conf.StoragePath
	simpleFlashRo   bool

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

func NewFirmwareService(ctx context.Context, dutAdapter common_utils.ServiceAdapterInterface, servoClient api.ServodServiceClient, req *api.ProvisionFirmwareRequest) (*FirmwareService, error) {
	simpleRequest := req.GetSimpleRequest()
	detailedRequest := req.GetDetailedRequest()
	if simpleRequest == nil && detailedRequest == nil {
		return nil, InvalidRequestErr("Specify SimpleRequest and DetailedRequest")
	}
	if simpleRequest != nil && detailedRequest != nil {
		panic(req) // shouldn't happen
	}
	useSimpleRequest := (simpleRequest != nil)

	board := req.GetBoard()
	if len(board) == 0 {
		return nil, InvalidRequestErr("FirmwareProvisionRequest: \"board\" field is required")
	}
	model := req.GetModel()
	if len(model) == 0 {
		return nil, InvalidRequestErr("FirmwareProvisionRequest: \"model\" field is required")
	}

	force := req.GetForce()
	useServo := req.GetUseServo()

	fws := FirmwareService{
		connection:       dutAdapter,
		board:            board,
		model:            model,
		force:            force,
		useServo:         useServo,
		useSimpleRequest: useSimpleRequest,
	}

	if useSimpleRequest {
		fws.simpleFlashRo = simpleRequest.FlashRo
		fws.simpleImagePath = simpleRequest.GetFirmwareImagePath()
		return nil, InvalidRequestErr("SimpleRequest is not implemented yet")
	} else {
		// Firmware may be updated in write-protected mode, where only 'rw' regions
		// would be update, or write-protection may be disabled (dangerous) in order
		// to update 'ro' regions.
		//
		// The only 'rw' firmware is the main one, aka AP firmware, which also syncs
		// EC 'rw'. It will be flashed with write protection turned on.
		fws.mainRwPath = detailedRequest.MainRwPayload.GetFirmwareImagePath()

		// Read-only firmware images include AP, EC, and PD firmware, and will be
		// flashed with write protection turned off.
		fws.mainRoPath = detailedRequest.MainRoPayload.GetFirmwareImagePath()
		fws.ecRoPath = detailedRequest.EcRoPayload.GetFirmwareImagePath()
		fws.pdRoPath = detailedRequest.PdRoPayload.GetFirmwareImagePath()

		fws.imagesMetadata = make(map[string]ImageArchiveMetadata)
	}

	if useServo {
		fws.prepareServoConnection(ctx, servoClient)
	}

	fws.PrintRequestInfo()

	if !fws.UpdateRo() && !fws.UpdateRw() {
		return nil, InvalidRequestErr("no paths to images specified")
	}

	return &fws, nil
}

// Confirms that cros-servod connection is functional, and fills the following
// fields in FirmwareService:
//   - servoConfig
//   - servoConnection
//   - ecChip
//   - servoPort
func (fws *FirmwareService) prepareServoConnection(ctx context.Context, servoClient api.ServodServiceClient) error {
	if servoClient == nil {
		return InvalidRequestErr("servo use is requested, but servo client not provided")
	}

	// Note: dut.GetChromeos().Servo.ServodAddress.Port is the port of cros-servod
	// service, we seem to be missing port of servod itself.
	// Always use default servod port 9999 for now.
	if fws.servoPort == 0 {
		fws.servoPort = 9999
	}

	fws.servoConnection = servoadapter.NewServoHostAdapterFromExecCmder(fws.board,
		fws.model,
		fws.servoPort,
		servoClient)

	// Ask servod for servo_type. This implicitly checks if servod is running
	// and servo connection is working.
	servoTypeStr, err := fws.servoConnection.GetVariable(ctx, "servo_type")
	if err != nil {

		return UnreachablePreProvisionErr("failed to get servo_type: %w. "+
			"Is servod running on port %v and connected to the DUT?",
			err, fws.servoPort) // TODO(sfrolov): add UnreachableCrosServodErr
	}

	// ask servod for serial number of the connected DUT.
	servoType := servo_lib.NewServoType(servoTypeStr)

	if servoType.IsMultipleServos() {
		// Handle dual servo.
		// We need CCD if ec_ro is set, otherwise, servo_micro will be faster.
		preferCCD := false
		if !fws.useSimpleRequest && fws.ecRoPath != nil {
			preferCCD = true
		}
		servoSubtypeStr := servoType.PickServoSubtype(preferCCD)
		servoType = servo_lib.NewServoType(servoSubtypeStr)
	}

	serial, err := fws.servoConnection.GetVariable(ctx, servoType.GetSerialNumberOption())
	if err != nil {
		return UnreachablePreProvisionErr("failed to get serial number variable: %w", err.Error()) // TODO: cros-servod is unreachable
	}

	// finally, get the correct config
	fws.servoConfig, err = servo_lib.GetServoConfig(fws.board, serial, servoType)
	if err != nil {
		return UnreachablePreProvisionErr("failed to get servo config: %w", err.Error()) // TODO: cros-servod is unreachable
	}

	fws.ecChip, err = fws.servoConnection.GetVariable(ctx, "ec_chip")
	if err != nil {
		return UnreachablePreProvisionErr("failed to get ec_chip variable: %w", err.Error()) // TODO: cros-servod is unreachable
	}
	return nil
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
	waitForReconnect := func(conn common_utils.ServiceAdapterInterface) error {
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

// CleanupOnFailure is called if one of service's states failes to Execute() and
// currenly cleans up the temporary files.
func (fws *FirmwareService) CleanupOnFailure(states []common_utils.ServiceState, executionErr error) error {
	return fws.DeleteArchiveDirectories()
}

func (fws *FirmwareService) DeleteArchiveDirectories() error {
	var cleanedDevice common_utils.ServiceAdapterInterface
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
		err := cleanedDevice.DeleteDirectory(context.Background(), imgMetadata.ArchiveDir)
		if err != nil {
			allErrors = append(allErrors, fmt.Sprintf("failed to delete %v: %v", imgMetadata.ArchiveDir, err))
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
func (fws FirmwareService) GetConnectionToFlashingDevice() common_utils.ServiceAdapterInterface {
	if fws.useServo {
		return fws.servoConnection
	} else {
		return fws.connection
	}
}

func (fws FirmwareService) IsServoUsed() bool {
	return fws.useServo
}
func (fws FirmwareService) IsForceUpdate() bool {
	return fws.force
}

func (fws FirmwareService) GetMainRwPath() string {
	return fws.mainRwPath.GetPath()
}
func (fws FirmwareService) GetMainRoPath() string {
	return fws.mainRoPath.GetPath()
}
func (fws FirmwareService) GetEcRoPath() string {
	return fws.ecRoPath.GetPath()
}
func (fws FirmwareService) GetPdRoPath() string {
	return fws.pdRoPath.GetPath()
}

// DownloadAndProcess downloads and extracts a provided archive,
// and stores the folder with contents in s.service.archiveFolders map.
func (fws FirmwareService) DownloadAndProcess(ctx context.Context, gspath string) error {
	connection := fws.GetConnectionToFlashingDevice()
	if _, alreadyDownloaded := fws.imagesMetadata[gspath]; !alreadyDownloaded {
		archiveMetadata, err := downloadAndProcessArchive(ctx, connection, gspath)
		if err != nil {
			log.Printf("[FW Provisioning: Prepare FW] failed to download and process %v: %v\n", gspath, err)
			return err
		} else {
			log.Printf("[FW Provisioning: Prepare FW] downloaded %v to %v. Files in archive: %v\n",
				gspath, archiveMetadata.ArchivePath, len(archiveMetadata.ListOfFiles))
		}
		fws.imagesMetadata[gspath] = *archiveMetadata
	}
	return nil
}

// GetImageMetadata returns (ImageArchiveMetadata, IsImageMetadataPresent)
func (fws FirmwareService) GetImageMetadata(gspath string) (ImageArchiveMetadata, bool) {
	metadata, ok := fws.imagesMetadata[gspath]
	return metadata, ok
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
