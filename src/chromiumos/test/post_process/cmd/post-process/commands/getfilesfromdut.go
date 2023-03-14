// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// GetFilesFromDUT pulls files from the dut and returns where its placed in the local fs.
func GetFilesFromDUT(logger *log.Logger, req *api.GetFilesFromDUTRequest, dutClient api.DutServiceClient) (*api.GetFilesFromDUTResponse, error) {
	return nil, status.Error(codes.Unimplemented, "GetFilesFromDUT unimplemented")

}
