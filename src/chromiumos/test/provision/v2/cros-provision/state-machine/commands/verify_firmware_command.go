// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"regexp"
	"strings"

	"go.chromium.org/chromiumos/config/go/test/api"
)

var firmwareManifestRegexp = regexp.MustCompile("FIRMWARE_MANIFEST_KEY='(.*)'")

type VerifyFirmwareCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewVerifyFirmwareCommand(ctx context.Context, cs *service.CrOSService) *VerifyFirmwareCommand {
	return &VerifyFirmwareCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *VerifyFirmwareCommand) Execute(log *log.Logger) error {
	log.Printf("Start VerifyFirmwareCommand Execute")

	expected, err := c.getAvailableFirmwareVersion()
	if err != nil {
		log.Printf("VerifyFirmwareCommand FAILED NON FATAL, %s", err)
		return nil
	}
	log.Printf("expected firmware %s", expected)
	actual, err := c.getCurrentFirmwareVersion()
	if err != nil {
		log.Printf("VerifyFirmwareCommand FAILED NON FATAL, %s", err)
		return nil
	}
	log.Printf("actual firmware %s", actual)
	if expected != actual {
		return fmt.Errorf("firmware version mismatch after update, expected: %s, actual: %s", expected, actual)
	}

	log.Printf("VerifyFirmwareCommand Success")

	return nil
}

// getAvailableFirmwareVersion read firmware manifest from current OS and extract available firmware version based on model.
func (c *VerifyFirmwareCommand) getAvailableFirmwareVersion() (string, error) {
	out, err := c.cs.Connection.RunCmd(c.ctx, common_utils.FirmwareUpdaterPath, []string{"--manifest"})
	if err != nil {
		return "", fmt.Errorf("getAvailableFirmwareVersion: failed to get firmware manifest, %s", err)
	}
	var manifest common_utils.FirmwareManifest
	if err := json.Unmarshal([]byte(out), &manifest); err != nil {
		return "", fmt.Errorf("getAvailableFirmwareVersion: failed to unmarshal firmware manifest, %s", err)
	}
	fwModel, err := c.getFirmwareTarget()
	if err != nil {
		return "", fmt.Errorf("getAvailableFirmwareVersion: failed to get firmware target %s", err)
	}
	if data, ok := manifest[fwModel]; ok {
		log.Printf("Available firmware from the new OS: %s.", data.Host.Versions.Rw)
		return data.Host.Versions.Rw, nil
	}
	return "", fmt.Errorf("getAvailableFirmwareVersion: failed to get firmware data of key %s from manifest, %s", fwModel, err)
}

// getFirmwareTarget returns firmware target of the DUT, which will be used to as key to fetch expected firmware from manifest.
func (c *VerifyFirmwareCommand) getFirmwareTarget() (string, error) {
	out, err := c.cs.Connection.RunCmd(c.ctx, "crosid", []string{})
	if err != nil {
		return "", err
	}
	fwLine := firmwareManifestRegexp.FindString(out)
	if fwLine != "" {
		return strings.TrimLeft(strings.TrimRight(fwLine, "'"), "FIRMWARE_MANIFEST_KEY='"), nil
	}
	return "", fmt.Errorf("getFirmwareTarget: unable to parse FIRMWARE_MANIFEST_KEY from crosid.")
}

// getCurrentFirmwareVersion read current system firmware version on the DUT.
func (c *VerifyFirmwareCommand) getCurrentFirmwareVersion() (string, error) {
	out, err := c.cs.Connection.RunCmd(c.ctx, "crossystem", []string{"fwid"})
	if err != nil {
		return "", fmt.Errorf("getCurrentFirmwareVersion: failed to read current system firmware, %s", err)
	}
	log.Printf("Current firmware on DUT: %s.", out)
	return out, nil
}

func (c *VerifyFirmwareCommand) Revert() error {
	return nil
}

func (c *VerifyFirmwareCommand) GetErrorMessage() string {
	return "firmware installed does not match with OS bundled firmware"
}

func (c *VerifyFirmwareCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_FIRMWARE_MISMATCH_POST_FIRMWARE_UPDATE
}
