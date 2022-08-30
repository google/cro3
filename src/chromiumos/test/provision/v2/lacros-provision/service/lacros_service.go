// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Container for the CrOSProvision state machine
package service

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	lacros_metadata "chromiumos/test/provision/v2/lacros-provision/lacros-metadata"
	"context"
	"fmt"
	"path"
	"regexp"

	conf "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
)

// LaCrOSService inherits ServiceInterface
type LaCrOSService struct {
	Connection          common_utils.ServiceAdapterInterface
	LaCrOSMetadata      *lacros_metadata.LaCrOSMetadata
	ImagePath           *conf.StoragePath
	Blocks              int
	OverwritePayload    *conf.StoragePath
	OverrideVersion     string
	OverrideInstallPath string
}

var versionRegex = regexp.MustCompile(`^(\d+\.)(\d+\.)(\d+\.)(\d+)$`)

func NewLaCrOSService(dut *lab_api.Dut, dutClient api.DutServiceClient, req *api.InstallRequest) (*LaCrOSService, error) {
	m, err := unpackMetadata(req)
	if err != nil {
		return nil, err
	}
	if m.OverrideVersion != "" {
		if !versionRegex.MatchString(m.OverrideVersion) {
			return nil, fmt.Errorf("failed to parse version: %v", m.OverrideVersion)
		}
	}
	return &LaCrOSService{
		Connection:          common_utils.NewServiceAdapter(dutClient, req.GetPreventReboot()),
		ImagePath:           req.ImagePath,
		OverwritePayload:    req.OverwritePayload,
		OverrideVersion:     m.OverrideVersion,
		OverrideInstallPath: m.OverrideInstallPath,
	}, nil
}

func NewLaCrOSServiceFromCrOSProvisionRequest(dutClient api.DutServiceClient, req *api.CrosProvisionRequest, pkg *api.ProvisionState_Package) *LaCrOSService {
	return &LaCrOSService{
		Connection:          common_utils.NewServiceAdapter(dutClient, req.ProvisionState.GetPreventReboot()),
		ImagePath:           pkg.GetPackagePath(),
		OverwritePayload:    req.GetProvisionState().GetSystemImage().GetOverwritePayload(),
		OverrideVersion:     "",
		OverrideInstallPath: "",
	}
}

// NewLaCrOSServiceFromExistingConnection is equivalent to the above constructor,
// but recycles a ServiceAdapter. Generally useful for tests.
func NewLaCrOSServiceFromExistingConnection(conn common_utils.ServiceAdapterInterface, imagePath *conf.StoragePath, overwritePayload *conf.StoragePath, overrideVersion string, overrideInstallPath string) LaCrOSService {
	return LaCrOSService{
		Connection:          conn,
		ImagePath:           imagePath,
		OverwritePayload:    overwritePayload,
		OverrideVersion:     overrideVersion,
		OverrideInstallPath: overrideInstallPath,
	}
}

// CleanupOnFailure is called if one of service's states failes to Execute() and
// should clean up the temporary files, and undo the execution, if feasible.
func (c *LaCrOSService) CleanupOnFailure(states []common_utils.ServiceState, executionErr error) error {
	// TODO: evaluate whether cleanup is needed.
	return nil
}

// unpackMetadata unpacks the Any metadata field into CrOSProvisionMetadata
func unpackMetadata(req *api.InstallRequest) (*api.LaCrOSProvisionMetadata, error) {
	m := api.LaCrOSProvisionMetadata{}
	if err := req.Metadata.UnmarshalTo(&m); err != nil {
		return &m, fmt.Errorf("improperly formatted input proto metadata, %s", err)
	}
	return &m, nil
}

/*
	The following run specific commands related to LaCrOS installation.
*/

func (l *LaCrOSService) GetComponentRootPath() string {
	return "/home/chronos/cros-components"
}

func (l *LaCrOSService) GetComponentPath() string {
	var cp string
	if l.OverrideInstallPath != "" {
		cp = l.OverrideInstallPath
	} else {
		cp = common_utils.LaCrOSRootComponentPath
	}
	return path.Join(cp, l.LaCrOSMetadata.Content.Version)
}

func (l *LaCrOSService) GetMetatadaPath() string {
	return path.Join(l.ImagePath.GetPath(), "metadata.json")
}

func (l *LaCrOSService) GetCompressedImagePath() string {
	return path.Join(l.ImagePath.GetPath(), "lacros_compressed.squash")
}

func (l *LaCrOSService) GetDeviceCompressedImagePath() string {
	return path.Join(l.ImagePath.GetPath(), "lacros.squash")
}

func (l *LaCrOSService) GetLocalImagePath() string {
	return path.Join(l.GetComponentPath(), "image.squash")
}

func (l *LaCrOSService) GetHashTreePath() string {
	return path.Join(l.GetComponentPath(), "hashtree")
}

func (l *LaCrOSService) GetTablePath() string {
	return path.Join(l.GetComponentPath(), "table")
}

func (l *LaCrOSService) GetManifestPath() string {
	return path.Join(l.GetComponentPath(), "imageloader.json")
}

func (l *LaCrOSService) GetComponentManifestPath() string {
	return path.Join(l.GetComponentPath(), "manifest.json")
}

func (l *LaCrOSService) GetLatestVersionPath() string {
	return path.Join(common_utils.LaCrOSRootComponentPath, "latest-version")
}

// writeToFile takes a string and writes its contents to a file on a DUT.
func (l *LaCrOSService) WriteToFile(ctx context.Context, data, outputPath string) error {
	if _, err := l.Connection.RunCmd(ctx, "echo", []string{
		fmt.Sprintf("'%s'", data), ">", outputPath,
	}); err != nil {
		return fmt.Errorf("failed to write data to file, %w", err)
	}
	return nil
}
