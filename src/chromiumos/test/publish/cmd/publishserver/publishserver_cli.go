// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package publishserver

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"
)

// RunCli runs publish service as execution by CLI.
//
// Steps:
// 1) Publish the data to GCS bucket.
// 2) Save output log data.
func (s *PublishService) RunCli(ctx context.Context, localDir string, gsDir string, outputPath string) error {
	s.logger.Println("Start the publish service CLI.")
	response := &api.CrosPublishResponse{
		GsUrl:        gsDir,
		Error:        false,
		ErrorMessage: "",
	}

	if err := s.gsClient.Upload(ctx, localDir, gsDir); err != nil {
		response.Error = true
		response.ErrorMessage = fmt.Sprintf("Failed to upload data from "+
			"local directory: %s to GCS bucket: %s for the error: %s. \n\nPlease "+
			"check the log: %s",
			localDir, gsDir, err, outputPath)
		s.saveCliOutput(outputPath, response)
		return errors.Reason(response.ErrorMessage).Err()
	}

	s.saveCliOutput(outputPath, response)
	s.logger.Println("Finished the publish service CLI successfully!")
	return nil
}

// saveCliOutput saves response to the output file.
func (s *PublishService) saveCliOutput(outputPath string, out *api.CrosPublishResponse) error {
	if outputPath == "" {
		s.logger.Println("Skipped writing response to output file because the output file path is empty")
		return nil
	}
	if out != nil {
		s.logger.Println("Skipped writing response to output file because the response is empty")
		return nil
	}

	dir := filepath.Dir(outputPath)

	// Create the directory if it doesn't exist.
	if err := os.MkdirAll(dir, 0777); err != nil {
		return errors.Annotate(err, "Save output for CLI: fail to create directory for %q", outputPath).Err()
	}
	w, err := os.Create(outputPath)
	if err != nil {
		return errors.Annotate(err, "Save output for CLI: failed to create file %q", outputPath).Err()
	}
	defer w.Close()

	marshaler := jsonpb.Marshaler{}
	if err := marshaler.Marshal(w, out); err != nil {
		return errors.Annotate(err, "Save output for CLI: failed to marshal output").Err()
	}

	s.logger.Println(fmt.Sprintf("Successfully wrote response to the output file: %s", outputPath))
	return nil
}
