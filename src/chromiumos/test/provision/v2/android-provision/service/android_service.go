// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package servicer is a container for the AndroidProvision state machine.
package service

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"

	common_utils "chromiumos/test/provision/v2/common-utils"
)

// AndroidPackage contains information about installed Android package.
type AndroidPackage struct {
	PackageName        string
	VersionCode        string
	UpdatedVersionCode string
}

// CIPDPackage wraps CIPD package proto and contains the resolved CIPD package info.
type CIPDPackage struct {
	PackageProto *api.CIPDPackage
	FilePath     string
	PackageName  string
	InstanceId   string
	VersionCode  string
}

// APKFile describes APK file.
type APKFile struct {
	Name          string
	GsPath        string
	ProvisionPath string
}

// ProvisionPackage contains information about provision package.
type ProvisionPackage struct {
	AndroidPackage *AndroidPackage
	CIPDPackage    *CIPDPackage
	APKFile        *APKFile
}

// DUTConnection has information about CrosDUT connection and DUT serial number.
type DUTConnection struct {
	AssociatedHost common_utils.ServiceAdapterInterface
	SerialNumber   string
}

// AndroidService inherits ServiceInterface
type AndroidService struct {
	DUT               *DUTConnection
	ProvisionPackages []*ProvisionPackage
	ProvisionDir      string
}

func NewAndroidService(dut *lab_api.Dut, dutClient api.DutServiceClient, req *api.InstallRequest) (*AndroidService, error) {
	m, err := unpackMetadata(req)
	if err != nil {
		return nil, err
	}
	dir, err := os.MkdirTemp("", "android_provision_")
	if err != nil {
		return nil, err
	}
	var p []*ProvisionPackage
	for _, pkgProto := range m.GetCipdPackages() {
		cipdPkg := &CIPDPackage{
			PackageProto: pkgProto,
		}
		p = append(p, &ProvisionPackage{CIPDPackage: cipdPkg})
	}
	return &AndroidService{
		DUT: &DUTConnection{
			AssociatedHost: common_utils.NewServiceAdapter(dutClient, true),
			SerialNumber:   dut.GetAndroid().GetSerialNumber(),
		},
		ProvisionDir:      dir,
		ProvisionPackages: p,
	}, nil
}

func NewAndroidServiceFromAndroidProvisionRequest(dutClient api.DutServiceClient, req *api.AndroidProvisionRequest) (*AndroidService, error) {
	dir, err := os.MkdirTemp("", "android_provision_")
	if err != nil {
		return nil, err
	}
	var p []*ProvisionPackage
	for _, pkgProto := range req.GetCipdPackages() {
		cipdPkg := &CIPDPackage{
			PackageProto: pkgProto,
		}
		p = append(p, &ProvisionPackage{CIPDPackage: cipdPkg})
	}
	return &AndroidService{
		DUT: &DUTConnection{
			AssociatedHost: common_utils.NewServiceAdapter(dutClient, true),
			SerialNumber:   req.GetDut().GetAndroid().GetSerialNumber(),
		},
		ProvisionDir:      dir,
		ProvisionPackages: p,
	}, nil
}

// NewAndroidServiceFromExistingConnection utilizes a given ServiceAdapter. Generally useful for tests.
func NewAndroidServiceFromExistingConnection(conn common_utils.ServiceAdapterInterface, dutSerialNumber string, pkgProtos []*api.CIPDPackage) (*AndroidService, error) {
	dir, err := os.MkdirTemp("", "android_provision_")
	if err != nil {
		return nil, err
	}
	var p []*ProvisionPackage
	for _, pkgProto := range pkgProtos {
		cipdPkg := &CIPDPackage{
			PackageProto: pkgProto,
		}
		p = append(p, &ProvisionPackage{CIPDPackage: cipdPkg})
	}
	return &AndroidService{
		DUT: &DUTConnection{
			AssociatedHost: conn,
			SerialNumber:   dutSerialNumber,
		},
		ProvisionDir:      dir,
		ProvisionPackages: p,
	}, nil
}

// CleanupOnFailure is called if one of service's states failes to Execute() and
// should clean up the temporary files, and undo the execution, if feasible.
func (svc *AndroidService) CleanupOnFailure(states []common_utils.ServiceState, executionErr error) error {
	os.RemoveAll(svc.ProvisionDir)
	ctx := context.Background()
	for _, pkg := range svc.ProvisionPackages {
		if apkFile := pkg.APKFile; apkFile.ProvisionPath != "" {
			svc.DUT.AssociatedHost.DeleteDirectory(ctx, filepath.Dir(apkFile.ProvisionPath))
		}
	}
	return nil
}

// unpackMetadata unpacks the Any metadata field into AndroidProvisionMetadata
func unpackMetadata(req *api.InstallRequest) (*api.AndroidProvisionMetadata, error) {
	m := api.AndroidProvisionMetadata{}
	if err := req.Metadata.UnmarshalTo(&m); err != nil {
		return &m, fmt.Errorf("improperly formatted input proto metadata, %s", err)
	}
	return &m, nil
}
