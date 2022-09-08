// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// package servo_lib provides servo-related variables, such as dut-controls
// to be run before and after flashing, and a programmer argument.
package servo_lib

import "fmt"

// ServoConfig structure holds the servo-related variables that are necessary
// for provisioning firmware over Servo.
type ServoConfig struct {
	// dut-controls to run before flashing.
	DutOn [][]string
	// dut-controls to run after flashing.
	DutOff [][]string
	// programmer (-p) argument for futility.
	Programmer string
	// extra arguments to provide to futility, such as --fast or --force.
	ExtraArgs []string
	// servo_type in use.
	ServoType ServoType
}

type UnsupportedServoError struct {
	ServoType ServoType
	Board     string
}

func (m *UnsupportedServoError) Error() string {
	return fmt.Sprintf("board %v does not support servo %v", m.Board, m.ServoType.string)
}

// GetServoConfig returns ServoConfig, that depends on the |board| and |servoType|,
// and contains variables, necessary to flash that setup over Servo. One of those
// variables is a programmer argument, which needs to include |servoSerial| - serial
// number of the given DUT.
// Returns an error if a given |board| cannot be flashed using given |servoType|.
func GetServoConfig(board, servoSerial string, servoType ServoType) (*ServoConfig, error) {
	dutOn := [][]string{{"cpu_fw_spi:on"}}
	dutOff := [][]string{{"cpu_fw_spi:off"}}
	programmer := ""
	extraArgs := []string{}
	if servoType.IsV2() {
		programmer = fmt.Sprintf("ft2232_spi:type=google-servo-v2,serial=%v", servoSerial)
	} else if servoType.IsMicro() || servoType.IsC2D2() {
		programmer = fmt.Sprintf("raiden_debug_spi:serial=%v", servoSerial)
	} else if servoType.IsCCD() {
		dutOn = nil
		dutOff = nil
		programmer = fmt.Sprintf("raiden_debug_spi:target=AP,serial=%v", servoSerial)
		// By default, futility will verify images by re-reading them,
		// but this is extremely slow on CCDs (roughly over 30 mins),
		// so we turn verification off with "--fast".
		// Verification doesn't save DUTs from bricking.
		extraArgs = []string{"--fast"}
	} else {
		return nil, &UnsupportedServoError{servoType, board}
	}
	return &ServoConfig{dutOn, dutOff, programmer, extraArgs, servoType}, nil
}
