// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package servo_lib

import (
	"fmt"
	"strings"
)

// ServoType is the used servo type, as reported by `dut-control servo_type`.
// ServoType determines arguments to use with futility when flashing.
type ServoType struct {
	string
}

func NewServoType(servo_type string) ServoType {
	return ServoType{servo_type}
}

func (s *ServoType) IsV2() bool {
	return strings.Contains(s.string, "servo_v2")
}
func (s *ServoType) IsV4() bool {
	return strings.Contains(s.string, "servo_v4")
}
func (s *ServoType) IsC2D2() bool {
	return strings.Contains(s.string, "c2d2")
}
func (s *ServoType) IsCCD() bool {
	return strings.Contains(s.string, "ccd")
}
func (s *ServoType) IsMicro() bool {
	return strings.Contains(s.string, "servo_micro")
}

func (s *ServoType) GetSerialNumberOption() string {
	if s.IsV4() && s.IsCCD() {
		return "ccd_serialname"
	}
	if s.IsV4() && s.IsMicro() {
		return "servo_micro_serialname"
	}
	return "serialname"
}

func (s *ServoType) IsMultipleServos() bool {
	return strings.Contains(s.string, "_and_")
}

// PickServoSubtype allows to pick a single servo from dual servo types,
// such as "servo_v4p1_with_servo_micro_and_ccd_cr50".
// PickServoSubtype assumes that the servo is dual, use IsMultipleServos()
// function to check for that.
// |preferCCD| tells the function to pick the CCD servo, otherwise other servo
// type (likely servo_micro) will be chosen. Example:
//
//	If preferCCD is true, string above will return "servo_v4p1_with_ccd_cr50".
//	If preferCCD is false, it will return "servo_v4p1_with_servo_micro".
func (s *ServoType) PickServoSubtype(preferCCD bool) string {
	withSplit := strings.Split(s.string, "_with_")
	if len(withSplit) <= 1 {
		return strings.Split(s.string, "_and_")[0]
	}

	// for "servo_v4p1_with_servo_micro_and_ccd_cr50" this would return "servo_v4p1"
	servoVer := withSplit[0]

	servoSubtypes := strings.Split(withSplit[1], "_and_")
	subtypeToUse := ""
	for _, servoSubType := range servoSubtypes {
		subtypeToUse = servoSubType
		isCCD := strings.Contains(servoSubType, "ccd")
		if isCCD && preferCCD {
			break
		}
		if !isCCD && !preferCCD {
			break
		}
	}

	return fmt.Sprintf("%v_with_%v", servoVer, subtypeToUse)
}
