// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"fmt"
	"strconv"
	"strings"

	"chromiumos/test/dut/cmd/cros-dut/dutssh"

	hwdesign "go.chromium.org/chromiumos/config/go/api"
	"go.chromium.org/chromiumos/config/go/test/api"
)

// cros_config returns an error for non-existent properties, so we'll ignore
// this and return empty string since many of the identity attributes are optional.
func crosConfigIdentity(c dutssh.CmdExecutor, property string) string {
	result, _ := c.RunCmd(fmt.Sprintf("cros_config /identity %s", property))
	return strings.TrimSpace(result.StdOut)
}

// DetectDeviceConfigID uses cros_config to probe a live device and retrieve
// unique device config identifiers, which can then be used to looking up config details.
// A reverse lookup effectively when device identity isn't known up front.
// This supports the local device use-case and also initial device onboarding in managed labs.
func DetectDeviceConfigID(c dutssh.CmdExecutor) *api.DetectDeviceConfigIdResponse {
	designScanConfig := &hwdesign.DesignConfigId_ScanConfig{}
	var failure string
	if match := crosConfigIdentity(c, "smbios-name-match"); len(match) > 0 {
		designScanConfig.FirmwareNameMatch = &hwdesign.DesignConfigId_ScanConfig_SmbiosNameMatch{
			SmbiosNameMatch: match,
		}
	} else if match := crosConfigIdentity(c, "device-tree-compatible-match"); len(match) > 0 {
		designScanConfig.FirmwareNameMatch = &hwdesign.DesignConfigId_ScanConfig_DeviceTreeCompatibleMatch{
			DeviceTreeCompatibleMatch: match,
		}
	} else {
		failure = "Failed to scan firmware identity for X86 (smbios-name-match) and ARM (device-tree-compatible-match)"
	}

	// FirmwareNameMatch is the only required bit ... all optional from here on
	if skuIDStr := crosConfigIdentity(c, "sku-id"); len(skuIDStr) > 0 {
		if skuID, err := strconv.ParseUint(skuIDStr, 10, 32); err == nil {
			designScanConfig.FirmwareSku = uint32(skuID)
		} else {
			failure = fmt.Sprintf("Unexpected value '%s' (non uint32) for sku-id", skuIDStr)
		}
	}

	brandScanConfig := &hwdesign.DeviceBrandId_ScanConfig{}
	if wlTag := crosConfigIdentity(c, "whitelabel-tag"); len(wlTag) > 0 {
		brandScanConfig.WhitelabelTag = wlTag
	}

	mfgScanConfig := &hwdesign.MfgConfigId_ScanConfig{}
	hwidResult, _ := c.RunCmd("crossystem hwid")
	hwid := strings.TrimSpace(hwidResult.StdOut)
	if len(hwid) > 0 {
		mfgScanConfig.Hwid = hwid
	}

	resp := &api.DetectDeviceConfigIdResponse{}
	if len(failure) == 0 {
		resp.Result = &api.DetectDeviceConfigIdResponse_Success_{
			Success: &api.DetectDeviceConfigIdResponse_Success{
				DetectedScanConfig: &hwdesign.DeviceConfigId_ScanConfig{
					DesignScanConfig: designScanConfig,
					BrandScanConfig:  brandScanConfig,
					MfgScanConfig:    mfgScanConfig,
				},
			},
		}
	} else {
		resp.Result = &api.DetectDeviceConfigIdResponse_Failure_{
			Failure: &api.DetectDeviceConfigIdResponse_Failure{
				ErrorMessage: failure,
			},
		}
	}

	return resp
}
