// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/util/common"
	"context"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
)

// GetFwInfo will gather fwinfo via crossystem. If any field is not found it will be returned with "None".
func GetFwInfo(logger *log.Logger, req *api.GetFWInfoRequest, dutClient api.DutServiceClient) (*api.GetFWInfoResponse, error) {
	roFWID, err := common.RunCmd(context.Background(), "crossystem", []string{"ro_fwid"}, dutClient)
	if err != nil {
		logger.Printf("get ro_fwid cmd FAILED: %s\n", err)
	}
	rwFWID, err := common.RunCmd(context.Background(), "crossystem", []string{"rw_fwid"}, dutClient)
	if err != nil {
		logger.Printf("get rw_fwid cmd FAILED: %s\n", err)
		rwFWID = "None"

	}
	kVersion, err := common.RunCmd(context.Background(), "uname", []string{"-r"}, dutClient)
	if err != nil {
		logger.Printf("get uname -r cmd FAILED: %s\n", err)
	}
	resp := &api.GetFWInfoResponse{RoFwid: roFWID, RwFwid: rwFWID, KernelVersion: kVersion}
	return resp, nil
}
