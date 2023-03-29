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
	"google.golang.org/protobuf/types/known/anypb"

	"chromiumos/test/provision/v2/android-provision/common"
	common_utils "chromiumos/test/provision/v2/common-utils"
)

// AndroidPackage contains information about installed Android package.
type AndroidPackage struct {
	PackageName        string
	VersionCode        string
	UpdatedVersionCode string
}

// OsBuildInfo contains information about Android OS build.
type OsBuildInfo struct {
	Id                 string
	IncrementalVersion string
}

// CIPDPackage wraps CIPD package proto and contains the resolved CIPD package info.
type CIPDPackage struct {
	PackageProto *api.CIPDPackage
	FilePath     string
	PackageName  string
	InstanceId   string
	VersionCode  string
}

// PkgFile defines package file to install.
type PkgFile struct {
	Name    string
	GsPath  string
	DutPath string
}

// ImagePath defines OS image file(s) to flash.
type ImagePath struct {
	GsPath string
	Files  []string
	// DUT directory containing the binary images.
	DutAndroidProductOut string
}

// ProvisionPackage contains information about provision package.
type ProvisionPackage struct {
	AndroidPackage *AndroidPackage
	CIPDPackage    *CIPDPackage
	APKFile        *PkgFile
}

// AndroidOS contains information about Android OS to install.
type AndroidOS struct {
	ImagePath        *ImagePath
	BuildInfo        *OsBuildInfo
	UpdatedBuildInfo *OsBuildInfo
}

// DUTConnection has information about CrosDUT connection and DUT serial number.
type DUTConnection struct {
	AssociatedHost common_utils.ServiceAdapterInterface
	SerialNumber   string
}

// AndroidService inherits ServiceInterface
type AndroidService struct {
	DUT               *DUTConnection
	OS                *AndroidOS
	ProvisionPackages []*ProvisionPackage
	ProvisionDir      string
}

func NewAndroidService(dut *lab_api.Dut, dutClient api.DutServiceClient, req *api.InstallRequest) (*AndroidService, error) {
	dir, err := os.MkdirTemp("", "android_provision_")
	if err != nil {
		return nil, err
	}
	svc := &AndroidService{
		DUT: &DUTConnection{
			AssociatedHost: common_utils.NewServiceAdapter(dutClient, true),
			SerialNumber:   dut.GetAndroid().GetSerialNumber(),
		},
		ProvisionDir: dir,
	}
	if err := svc.UnmarshalRequestMetadata(req); err != nil {
		return nil, err
	}
	return svc, nil
}

func NewAndroidServiceFromAndroidProvisionRequest(dutClient api.DutServiceClient, req *api.AndroidProvisionRequest) (*AndroidService, error) {
	dir, err := os.MkdirTemp("", "android_provision_")
	if err != nil {
		return nil, err
	}
	var androidOs *AndroidOS
	var p []*ProvisionPackage
	if ps := req.GetProvisionState(); ps != nil {
		if osImage := ps.GetAndroidOsImage(); osImage != nil {
			switch v := osImage.GetLocationOneof().(type) {
			case *api.AndroidOsImage_GsPath:
				if imagePath := parseGsPath(osImage.GetGsPath()); imagePath != nil {
					androidOs = &AndroidOS{ImagePath: imagePath}
				}
			default:
				return nil, fmt.Errorf("unknown Android OS image type: %T", v)
			}
		}
		for _, pkgProto := range ps.GetCipdPackages() {
			cipdPkg := &CIPDPackage{
				PackageProto: pkgProto,
			}
			p = append(p, &ProvisionPackage{CIPDPackage: cipdPkg})
		}
	}
	return &AndroidService{
		DUT: &DUTConnection{
			AssociatedHost: common_utils.NewServiceAdapter(dutClient, true),
			SerialNumber:   req.GetDut().GetAndroid().GetSerialNumber(),
		},
		OS:                androidOs,
		ProvisionDir:      dir,
		ProvisionPackages: p,
	}, nil
}

// NewAndroidServiceFromExistingConnection utilizes a given ServiceAdapter. Generally useful for tests.
func NewAndroidServiceFromExistingConnection(conn common_utils.ServiceAdapterInterface, dutSerialNumber string, osImage *api.AndroidOsImage, pkgProtos []*api.CIPDPackage) (*AndroidService, error) {
	dir, err := os.MkdirTemp("", "android_provision_")
	if err != nil {
		return nil, err
	}
	var androidOs *AndroidOS
	var p []*ProvisionPackage
	if osImage != nil {
		switch v := osImage.GetLocationOneof().(type) {
		case *api.AndroidOsImage_GsPath:
			if imagePath := parseGsPath(osImage.GetGsPath()); imagePath != nil {
				androidOs = &AndroidOS{ImagePath: imagePath}
			}
		default:
			return nil, fmt.Errorf("unknown Android OS image type: %T", v)
		}
	}
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
		OS:                androidOs,
		ProvisionDir:      dir,
		ProvisionPackages: p,
	}, nil
}

// CleanupOnFailure is called if one of service's states failes to Execute() and
// should clean up the temporary files, and undo the execution, if feasible.
func (svc *AndroidService) CleanupOnFailure(states []common_utils.ServiceState, executionErr error) error {
	os.RemoveAll(svc.ProvisionDir)
	ctx := context.Background()
	if svc.OS != nil && svc.OS.ImagePath.DutAndroidProductOut != "" {
		svc.DUT.AssociatedHost.DeleteDirectory(ctx, svc.OS.ImagePath.DutAndroidProductOut)
	}
	for _, pkg := range svc.ProvisionPackages {
		if apkFile := pkg.APKFile; apkFile.DutPath != "" {
			svc.DUT.AssociatedHost.DeleteDirectory(ctx, filepath.Dir(apkFile.DutPath))
		}
	}
	return nil
}

// MarshalResponseMetadata packs AndroidProvisionResponseMetadata into the Any message type.
func (svc *AndroidService) MarshalResponseMetadata() (*anypb.Any, error) {
	resp := &api.AndroidProvisionResponseMetadata{}
	if osImage := svc.OS; osImage != nil && osImage.UpdatedBuildInfo != nil {
		resp.InstalledAndroidOs = &api.InstalledAndroidOS{
			BuildId:            osImage.UpdatedBuildInfo.Id,
			IncrementalVersion: osImage.UpdatedBuildInfo.IncrementalVersion,
		}
	}
	for _, pkg := range svc.ProvisionPackages {
		if ap := pkg.AndroidPackage; ap != nil && ap.UpdatedVersionCode != "" {
			installedPkg := &api.InstalledAndroidPackage{
				Name:        ap.PackageName,
				VersionCode: ap.UpdatedVersionCode,
			}
			resp.InstalledAndroidPackages = append(resp.InstalledAndroidPackages, installedPkg)
		}
	}
	return anypb.New(resp)
}

// UnmarshalRequestMetadata unpacks the Any metadata field into AndroidProvisionRequestMetadata
func (svc *AndroidService) UnmarshalRequestMetadata(req *api.InstallRequest) error {
	m := api.AndroidProvisionRequestMetadata{}
	if err := req.Metadata.UnmarshalTo(&m); err != nil {
		return fmt.Errorf("improperly formatted input proto metadata, %s", err)
	}
	if osImage := m.GetAndroidOsImage(); osImage != nil {
		switch v := osImage.GetLocationOneof().(type) {
		case *api.AndroidOsImage_GsPath:
			if imagePath := parseGsPath(osImage.GetGsPath()); imagePath != nil {
				svc.OS = &AndroidOS{ImagePath: imagePath}
			}
		default:
			return fmt.Errorf("unknown Android OS image type: %T", v)
		}
	}
	for _, pkgProto := range m.GetCipdPackages() {
		cipdPkg := &CIPDPackage{PackageProto: pkgProto}
		svc.ProvisionPackages = append(svc.ProvisionPackages, &ProvisionPackage{CIPDPackage: cipdPkg})
	}
	return nil
}

func parseGsPath(gsPathProto *api.GsPath) *ImagePath {
	if gsPathProto == nil {
		return nil
	}
	bucketName := gsPathProto.GetBucket()
	if bucketName == "" {
		bucketName = common.GSImageBucketName
	}
	gsPath := "gs://" + filepath.Join(bucketName, gsPathProto.GetFolder(), gsPathProto.GetFile())
	if gsPathProto.GetFile() == "" {
		gsPath += "/"
	}
	return &ImagePath{
		GsPath: gsPath,
	}
}
