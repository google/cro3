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

// GetFilesFromDUT pulls files from the dut and returns where its placed in the local fs.
func GetFilesFromDUT(logger *log.Logger, req *api.GetFilesFromDUTRequest, dutClient api.DutServiceClient) (*api.GetFilesFromDUTResponse, error) {
	testInfos := []*api.FileMap{}
	for _, f := range req.Files {
		dest, err := common.GetFile(context.Background(), f, dutClient)
		if err == nil {
			logger.Printf("Fetched: %s\n", f)

			testInfos = append(testInfos, &api.FileMap{
				FileName:     f,
				FileLocation: dest,
			})
		} else {
			logger.Printf("Unable to fetch file %s with err: %s\n", f, err)
			testInfos = append(testInfos, &api.FileMap{
				FileName:     f,
				FileLocation: "",
			})
		}

	}

	resp := &api.GetFilesFromDUTResponse{FileMap: testInfos}
	return resp, nil
}
