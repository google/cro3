// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Provides functionality to connect to other CFT services.
package cli

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"fmt"

	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
	"google.golang.org/grpc"
)

func connectToDutServer(ipEndpointAddr *lab_api.IpEndpoint) (*common_utils.ServiceAdapter, error) {
	dutServAddr, err := ipEndpointToHostPort(ipEndpointAddr)
	if err != nil {
		return nil, fmt.Errorf("failed to parse IpEndpoint of Dut Server: %w", err)
	}
	dutConn, err := grpc.Dial(dutServAddr, grpc.WithInsecure())
	if err != nil {
		return nil, fmt.Errorf("failed to connect to Dut Server: %w", err)
	}
	dutServerAdapter := common_utils.NewServiceAdapter(
		api.NewDutServiceClient(dutConn), false /*noReboot*/)
	return &dutServerAdapter, nil
}

func connectToCrosServod(ipEndpointAddr *lab_api.IpEndpoint) (api.ServodServiceClient, error) {
	crosServodAddr, err := ipEndpointToHostPort(ipEndpointAddr)
	if err != nil {
		return nil, fmt.Errorf("failed to parse IpEndpoint of cros-servod: %w", err)
	}
	servodConn, err := grpc.Dial(crosServodAddr, grpc.WithInsecure())
	if err != nil {
		return nil, fmt.Errorf("failed to connect to cros-servod: %w", err)
	}
	servodServiceClient := api.NewServodServiceClient(servodConn)
	return servodServiceClient, nil
}
