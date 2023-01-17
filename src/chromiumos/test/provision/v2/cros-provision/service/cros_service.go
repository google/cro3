// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Container for the CrOSProvision state machine
package service

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/common-utils/metadata"
	"context"
	"fmt"

	conf "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
)

// CrOSService inherits ServiceInterface
type CrOSService struct {
	Connection        common_utils.ServiceAdapterInterface
	MachineMetadata   metadata.MachineMetadata
	ImagePath         *conf.StoragePath
	OverwritePayload  *conf.StoragePath
	PreserverStateful bool
	DlcSpecs          []*api.CrOSProvisionMetadata_DLCSpec
	UpdateFirmware    bool
	UpdateCros        bool
}

func NewCrOSService(dut *lab_api.Dut, dutClient api.DutServiceClient, req *api.InstallRequest) (*CrOSService, error) {
	m, err := unpackMetadata(req)
	if err != nil {
		return nil, err
	}
	return &CrOSService{
		Connection:        common_utils.NewServiceAdapter(dutClient, req.GetPreventReboot()),
		ImagePath:         req.ImagePath,
		OverwritePayload:  req.OverwritePayload,
		PreserverStateful: m.PreserveStateful,
		DlcSpecs:          m.DlcSpecs,
		MachineMetadata:   metadata.MachineMetadata{},
		UpdateFirmware:    m.UpdateFirmware,
		UpdateCros:        true, // Force this true by default
	}, nil
}

func NewCrOSServiceFromCrOSProvisionRequest(dutClient api.DutServiceClient, req *api.CrosProvisionRequest) *CrOSService {
	var dlcSpecs []*api.CrOSProvisionMetadata_DLCSpec
	for _, id := range req.GetProvisionState().GetSystemImage().GetDlcs() {
		dlcSpec := &api.CrOSProvisionMetadata_DLCSpec{
			Id: id.Value,
		}
		dlcSpecs = append(dlcSpecs, dlcSpec)
	}
	return &CrOSService{
		Connection:        common_utils.NewServiceAdapter(dutClient, req.GetProvisionState().GetPreventReboot()),
		ImagePath:         req.GetProvisionState().SystemImage.SystemImagePath,
		OverwritePayload:  req.GetProvisionState().GetSystemImage().GetOverwritePayload(),
		PreserverStateful: false,
		DlcSpecs:          dlcSpecs,
		MachineMetadata:   metadata.MachineMetadata{},
		UpdateFirmware:    req.GetProvisionState().UpdateFirmware,
		UpdateCros:        true, // Force this true by default

	}
}

// NewCrOSServiceFromExistingConnection is equivalent to the above constructor,
// but recycles a ServiceAdapter. Generally useful for tests.
func NewCrOSServiceFromExistingConnection(conn common_utils.ServiceAdapterInterface, imagePath *conf.StoragePath, overwritePayload *conf.StoragePath, preserverStateful bool, dlcSpecs []*api.CrOSProvisionMetadata_DLCSpec, updateFirmware bool) CrOSService {
	return CrOSService{
		Connection:        conn,
		ImagePath:         imagePath,
		OverwritePayload:  overwritePayload,
		PreserverStateful: preserverStateful,
		DlcSpecs:          dlcSpecs,
		MachineMetadata:   metadata.MachineMetadata{},
		UpdateFirmware:    updateFirmware,
		UpdateCros:        true, // Force this true by default

	}
}

// CleanupOnFailure is called if one of service's states fails to Execute() and
// should clean up the temporary files, and undo the execution, if feasible.
func (c *CrOSService) CleanupOnFailure(states []common_utils.ServiceState, executionErr error) error {
	// TODO: evaluate whether cleanup is needed.
	return nil
}

const pipeStatusHandler = `
pipestatus=("${PIPESTATUS[@]}")
if [[ "${pipestatus[0]}" -ne 0 ]]; then
  echo "$(date --rfc-3339=seconds) ERROR: Fetching %[1]s failed." >&2
  exit 1
elif [[ "${pipestatus[1]}" -ne 0 ]]; then
  echo "$(date --rfc-3339=seconds) ERROR: Decompressing %[1]s failed." >&2
  exit 1
elif [[ "${pipestatus[2]}" -ne 0 ]]; then
  echo "$(date --rfc-3339=seconds) ERROR: Writing to %[2]s failed." >&2
  exit 1
fi`

// InstallZippedImage installs a remote zipped image to disk.
func (c *CrOSService) InstallZippedImage(ctx context.Context, remoteImagePath string, outputFile string) error {
	if c.ImagePath.HostType == conf.StoragePath_LOCAL || c.ImagePath.HostType == conf.StoragePath_HOSTTYPE_UNSPECIFIED {
		return fmt.Errorf("only GS copying is implemented")
	}
	err := c.Connection.PipeData(ctx,
		common_utils.BucketJoin(c.ImagePath.GetPath(), remoteImagePath),
		fmt.Sprintf("gzip -d | %s %s", fmt.Sprintf("dd of=%s obs=2M", outputFile), fmt.Sprintf(pipeStatusHandler, c.ImagePath.GetPath(), outputFile)),
	)
	if err != nil {
		return fmt.Errorf("failed to install image, %w", err)
	}
	return nil
}

// unpackMetadata unpacks the Any metadata field into CrOSProvisionMetadata
func unpackMetadata(req *api.InstallRequest) (*api.CrOSProvisionMetadata, error) {
	m := api.CrOSProvisionMetadata{}
	if err := req.Metadata.UnmarshalTo(&m); err != nil {
		return &m, fmt.Errorf("improperly formatted input proto metadata, %s", err)
	}
	return &m, nil
}
