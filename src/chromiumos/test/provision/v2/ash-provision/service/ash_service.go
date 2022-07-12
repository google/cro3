// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Container for the CrOSProvision state machine
package service

import (
	common_utils "chromiumos/test/provision/v2/common-utils"

	conf "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
)

// AShService inherits ServiceInterface
type AShService struct {
	Connection       common_utils.ServiceAdapterInterface
	ImagePath        *conf.StoragePath
	OverwritePayload *conf.StoragePath
}

func NewAShService(dut *lab_api.Dut, dutClient api.DutServiceClient, req *api.InstallRequest) (*AShService, error) {
	return &AShService{
		Connection:       common_utils.NewServiceAdapter(dut, dutClient, req.GetPreventReboot()),
		ImagePath:        req.ImagePath,
		OverwritePayload: req.OverwritePayload,
	}, nil
}

func NewAShServiceFromCrOSProvisionRequest(dutClient api.DutServiceClient, req *api.CrosProvisionRequest, pkg *api.ProvisionState_Package) *AShService {
	return &AShService{
		Connection:       common_utils.NewServiceAdapter(req.Dut, dutClient, req.ProvisionState.GetPreventReboot()),
		ImagePath:        pkg.GetPackagePath(),
		OverwritePayload: req.GetProvisionState().GetSystemImage().GetOverwritePayload(),
	}
}

// NewAShServiceFromExistingConnection is equivalent to the above constructor,
// but recycles a ServiceAdapter. Generally useful for tests.
func NewAShServiceFromExistingConnection(conn common_utils.ServiceAdapterInterface, imagePath *conf.StoragePath, overwritePayload *conf.StoragePath, overrideVersion string, overrideInstallPath string) AShService {
	return AShService{
		Connection:       conn,
		ImagePath:        imagePath,
		OverwritePayload: overwritePayload,
	}
}

// CleanupOnFailure is called if one of service's states failes to Execute() and
// should clean up the temporary files, and undo the execution, if feasible.
func (c *AShService) CleanupOnFailure(states []common_utils.ServiceState, executionErr error) error {
	// TODO: evaluate whether cleanup is needed.
	return nil
}

func (c *AShService) GetStagingDirectory() string {
	return "/tmp/_provisioning_service_chrome_deploy"
}

func (c *AShService) GetTargetDir() string {
	return "/opt/google/chrome"
}
func (c *AShService) GetAutotestDir() string {
	return "/usr/local/autotest/deps/chrome_test/test_src/out/Release/"
}
func (c *AShService) GetTastDir() string {
	return "/usr/local/libexec/chrome-binary-tests/"
}
