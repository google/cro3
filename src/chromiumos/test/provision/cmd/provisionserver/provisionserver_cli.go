// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package provisionserver

import (
	"context"
	"os"
	"path/filepath"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
	"go.chromium.org/luci/common/errors"
)

// runCLI runs provision as execution by CLI.
//
// Steps:
// 1) Read input data.
// 2) Execute provisioning.
// 3) Save output data.
func (s *provision) RunCLI(ctx context.Context, state *api.ProvisionState, outputPath string) error {
	out := &api.CrosProvisionResponse{
		Id: &lab_api.Dut_Id{
			Value: s.dut.GetId().GetValue(),
		},
		Outcome: &api.CrosProvisionResponse_Success{},
	}
	defer saveCLIOutput(outputPath, out)

	if fr, err := s.installState(ctx, state, nil); err != nil {
		out.Outcome = &api.CrosProvisionResponse_Failure{
			Failure: fr,
		}
		return errors.Annotate(err, "run CLI").Err()
	}
	s.logger.Println("Finished successfully!")
	return nil
}

// saveCLIOutput saves response to the output file.
func saveCLIOutput(outputPath string, out *api.CrosProvisionResponse) error {
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
