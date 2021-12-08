// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// package servo_lib provides servo-related variables, such as dut-controls
// to be run before and after flashing, and a programmer argument.
package servo_lib

import "fmt"

type ServoConfig struct {
	dut_on     [][]string
	dut_off    [][]string
	programmer string
}

type UnsupportedServoError struct {
	servoType ServoType
	board     string
}

func (m *UnsupportedServoError) Error() string {
	return fmt.Sprintf("board %v does not support servo %v", m.board, m.servoType.string)
}

func GetServoConfig(board, servoSerial string, servoType ServoType) (*ServoConfig, error) {
	dut_on := [][]string{{"cpu_fw_spi:on"}}
	dut_off := [][]string{{"cpu_fw_spi:off"}}
	programmer := ""
	if servoType.IsV2() {
		programmer = fmt.Sprintf("ft2232_spi:type=google-servo-v2,serial=%v", servoSerial)
	} else if servoType.IsMicro() || servoType.IsC2D2() {
		programmer = fmt.Sprintf("raiden_debug_spi:serial=%v", servoSerial)
	} else if servoType.IsCCD() {
		dut_on = nil
		dut_off = nil
		programmer = fmt.Sprintf("raiden_debug_spi:target=AP,serial=%v", servoSerial)
	} else {
		return nil, &UnsupportedServoError{servoType, board}
	}
	return &ServoConfig{dut_on, dut_off, programmer}, nil
}
