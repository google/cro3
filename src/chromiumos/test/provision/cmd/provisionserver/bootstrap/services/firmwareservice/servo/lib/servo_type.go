// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package servo_lib

import "strings"

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
