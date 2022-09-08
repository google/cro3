// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package internal

import (
	"fmt"
	"testing"

	"chromiumos/test/dut/cmd/cros-dut/dutssh"
)

type FakeCmdExecutor struct {
	CmdResults map[string]*dutssh.CmdResult
}

func (e FakeCmdExecutor) RunCmd(cmd string) (*dutssh.CmdResult, error) {
	result, exists := e.CmdResults[cmd]
	if exists {
		return result, nil
	}
	// cros_config returns 1 for non-existent properties, so mimic that
	return cmdResult("", 1), nil
}

func cmdResult(stdout string, returnCode int32) *dutssh.CmdResult {
	return &dutssh.CmdResult{
		StdOut:     stdout,
		ReturnCode: returnCode,
	}
}

func TestFirmwareNameOnlyX86(t *testing.T) {
	fakeFwName := "Fake"
	fakeCmdExecutor := FakeCmdExecutor{
		map[string]*dutssh.CmdResult{
			"cros_config /identity smbios-name-match": cmdResult(fakeFwName, 0),
		},
	}

	result := DetectDeviceConfigID(fakeCmdExecutor).GetSuccess().DetectedScanConfig
	if result.DesignScanConfig.GetSmbiosNameMatch() != fakeFwName {
		t.Fatalf("Expected: %s, got: %s", fakeFwName, result.DesignScanConfig.GetSmbiosNameMatch())
	}
}

func TestFirmwareNameOnlyArm(t *testing.T) {
	fakeFwName := "Fake"
	fakeCmdExecutor := FakeCmdExecutor{
		map[string]*dutssh.CmdResult{
			"cros_config /identity device-tree-compatible-match": cmdResult(fakeFwName, 0),
		},
	}

	result := DetectDeviceConfigID(fakeCmdExecutor).GetSuccess().DetectedScanConfig
	if result.DesignScanConfig.GetDeviceTreeCompatibleMatch() != fakeFwName {
		t.Fatalf("Expected: %s, got: %s", fakeFwName, result.DesignScanConfig.GetSmbiosNameMatch())
	}
}

func TestOptionalIdentifers(t *testing.T) {
	fakeFwName := "Fake"
	skuID := 87
	wlTag := "wlTag"
	hwid := "FFFF FFFF FFFF"
	fakeCmdExecutor := FakeCmdExecutor{
		map[string]*dutssh.CmdResult{
			"cros_config /identity smbios-name-match": cmdResult(fakeFwName, 0),
			"cros_config /identity sku-id":            cmdResult(fmt.Sprintf("%d", skuID), 0),
			"cros_config /identity whitelabel-tag":    cmdResult(wlTag, 0),
			"crossystem hwid":                         cmdResult(hwid, 0),
		},
	}

	result := DetectDeviceConfigID(fakeCmdExecutor).GetSuccess().DetectedScanConfig
	if result.DesignScanConfig.GetSmbiosNameMatch() != fakeFwName {
		t.Fatalf("Expected: %s, got: %s", fakeFwName, result.DesignScanConfig.GetSmbiosNameMatch())
	}
	if result.DesignScanConfig.GetFirmwareSku() != uint32(skuID) {
		t.Fatalf("Expected: %d, got: %d", skuID, result.DesignScanConfig.GetFirmwareSku())
	}
	if result.BrandScanConfig.GetWhitelabelTag() != wlTag {
		t.Fatalf("Expected: %s, got: %s", wlTag, result.BrandScanConfig.GetWhitelabelTag())
	}
	if result.MfgScanConfig.GetHwid() != hwid {
		t.Fatalf("Expected: %s, got: %s", hwid, result.MfgScanConfig.GetHwid())
	}
}

func TestNoFirmwareNameErrors(t *testing.T) {
	fakeCmdExecutor := FakeCmdExecutor{
		map[string]*dutssh.CmdResult{},
	}

	errorMessage := DetectDeviceConfigID(fakeCmdExecutor).GetFailure().ErrorMessage
	if len(errorMessage) == 0 {
		t.Fatalf("Expected failure for missing fw name")
	}
}

func TestInvalidSkuFormatErrors(t *testing.T) {
	fakeFwName := "Fake"
	invalidSku := "NaN"
	fakeCmdExecutor := FakeCmdExecutor{
		map[string]*dutssh.CmdResult{
			"cros_config /identity smbios-name-match": cmdResult(fakeFwName, 0),
			"cros_config /identity sku-id":            cmdResult(invalidSku, 0),
		},
	}

	errorMessage := DetectDeviceConfigID(fakeCmdExecutor).GetFailure().ErrorMessage
	if len(errorMessage) == 0 {
		t.Fatalf("Expected failure for invalid sku format")
	}
}
