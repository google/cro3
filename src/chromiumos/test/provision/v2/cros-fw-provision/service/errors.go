// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package firmwareservice

import (
	"fmt"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type any interface{}

type FirmwareProvisionError struct {
	Status api.ProvisionFirmwareResponse_Status
	Err    error
}

func (fe *FirmwareProvisionError) Error() string {
	return fmt.Sprintf("%v: %v", fe.Status.String(), fe.Err)
}

func InvalidRequestErr(format string, a ...any) *FirmwareProvisionError {
	return &FirmwareProvisionError{
		Status: api.ProvisionFirmwareResponse_STATUS_INVALID_REQUEST,
		Err:    fmt.Errorf(format, a),
	}
}

func UnreachablePreProvisionErr(format string, a ...any) *FirmwareProvisionError {
	return &FirmwareProvisionError{
		Status: api.ProvisionFirmwareResponse_STATUS_DUT_UNREACHABLE_PRE_PROVISION,
		Err:    fmt.Errorf(format, a),
	}
}

func UpdateFirmwareFailedErr(format string, a ...any) *FirmwareProvisionError {
	return &FirmwareProvisionError{
		Status: api.ProvisionFirmwareResponse_STATUS_UPDATE_FIRMWARE_FAILED,
		Err:    fmt.Errorf(format, a),
	}
}

func FirmwareMismatchPostProvisionErr(format string, a ...any) *FirmwareProvisionError {
	return &FirmwareProvisionError{
		Status: api.ProvisionFirmwareResponse_STATUS_FIRMWARE_MISMATCH_POST_FIRMWARE_UPDATE,
		Err:    fmt.Errorf(format, a),
	}
}

func UnreachablePostProvisionErr(format string, a ...any) *FirmwareProvisionError {
	return &FirmwareProvisionError{
		Status: api.ProvisionFirmwareResponse_STATUS_DUT_UNREACHABLE_POST_FIRMWARE_UPDATE,
		Err:    fmt.Errorf(format, a),
	}
}
