// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Firmware constants and common types
package common_utils

const (
	FirmwareUpdaterPath              = "/usr/sbin/chromeos-firmwareupdate"
	CrossystemCurrentFirmwareSlotKey = "mainfw_act"
	CrossystemNextFirmwareSlotKey    = "fw_try_next"
)

type FirmwareManifest map[string]FirmwareManifestData

type FirmwareManifestData struct {
	Host struct {
		Versions struct {
			Ro string `json:"ro"`
			Rw string `json:"rw"`
		} `json:"versions"`
		Keys struct {
			Root     string `json:"root"`
			Recovery string `json:"recovery"`
		} `json:"keys"`
		Image string `json:"image"`
	} `json:"host"`
	Ec struct {
		Versions struct {
			Ro string `json:"ro"`
			Rw string `json:"rw"`
		} `json:"versions"`
		Image string `json:"image"`
	} `json:"ec"`
	SignatureId string `json:"signature_id"`
}
