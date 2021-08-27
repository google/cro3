// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"context"
	"io/ioutil"
	"os"
	"path/filepath"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"
)

// runCLI runs provision as execution by CLI.
//
// Steps:
// 1) Read input data.
// 2) Execute provisioning.
// 3) Save output data.
func (s *provision) runCLI(ctx context.Context, inputPath, outputPath string) error {
	// Request provisded as for CLI.
	state := &api.ProvisionState{}
	if err := readCLIInput(inputPath, state); err != nil {
		return errors.Annotate(err, "run CLI").Err()
	}
	out := &api.InstallCrosResponse{
		Outcome: &api.InstallCrosResponse_Success{},
	}
	defer saveCLIOutput(outputPath, out)

	fr, err := s.installState(ctx, state, nil)
	if err != nil {
		out = &api.InstallCrosResponse{
			Outcome: &api.InstallCrosResponse_Failure{
				Failure: fr,
			},
		}
		return errors.Annotate(err, "run CLI").Err()
	}
	s.logger.Println("Finished successfully!")
	return nil
}

// readCLIInput reads Provisionstate from the input file.
func readCLIInput(inputPath string, in *api.ProvisionState) error {
	b, err := ioutil.ReadFile(inputPath)
	if err != nil {
		return errors.Annotate(err, "read input: fail to read file %q", inputPath).Err()
	}
	err = jsonpb.Unmarshal(bytes.NewReader(b), in)
	return errors.Annotate(err, "read input: failed unmarshal").Err()
}

// saveCLIOutput saves response to the output file.
func saveCLIOutput(outputPath string, out *api.InstallCrosResponse) error {
	if outputPath != "" && out != nil {
		dir := filepath.Dir(outputPath)
		// Create the directory if it doesn't exist.
		if err := os.MkdirAll(dir, 0777); err != nil {
			return errors.Annotate(err, "save output: fail to create directory for %q", outputPath).Err()
		}
		w, err := os.Create(outputPath)
		if err != nil {
			return errors.Annotate(err, "save output: failed to create file %q", outputPath).Err()
		}
		defer w.Close()

		marshaler := jsonpb.Marshaler{}
		if err := marshaler.Marshal(w, out); err != nil {
			return errors.Annotate(err, "save output: failed to marshal output").Err()
		}
	}
	return nil
}
