// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package device implements utilities to extract device information.
package device

import (
	"testing"

	"go.chromium.org/chromiumos/config/go/test/api"
	labapi "go.chromium.org/chromiumos/config/go/test/lab/api"
)

type expectEndpointResult struct {
	ip       *labapi.IpEndpoint
	expected string
}

// TestAddress the function Address to return the addresses of DUTs.
func TestAddress(t *testing.T) {
	data := []expectEndpointResult{
		{
			ip:       &labapi.IpEndpoint{Address: "127.0.0.1", Port: 0},
			expected: "127.0.0.1",
		},
		{
			ip:       &labapi.IpEndpoint{Address: "0:0:0:0:0:ffff:7f00:1", Port: 2},
			expected: "[0:0:0:0:0:ffff:7f00:1]:2",
		},
		{
			ip:       &labapi.IpEndpoint{Address: "0:0:0:0:0:ffff:7f00:1", Port: 0},
			expected: "0:0:0:0:0:ffff:7f00:1",
		},
		{
			ip:       &labapi.IpEndpoint{Address: "chromeos6-row17-rack5-host15.cros.corp.google.com", Port: 0},
			expected: "chromeos6-row17-rack5-host15.cros.corp.google.com",
		},
		{
			ip:       &labapi.IpEndpoint{Address: "chromeos6-row17-rack5-host15", Port: 2555},
			expected: "chromeos6-row17-rack5-host15:2555",
		},
	}

	for _, d := range data {
		device := api.CrosTestRequest_Device{
			Dut: &labapi.Dut{
				Id:      &labapi.Dut_Id{Value: "AnyId"},
				DutType: &labapi.Dut_Chromeos{Chromeos: &labapi.Dut_ChromeOS{Ssh: d.ip}},
			},
		}
		got, err := Address(&device)
		if err != nil {
			t.Errorf("Cannot get address for dut %v: %v", device, err)
		}
		if got != d.expected {
			t.Errorf("Got %q from Address; wanted:%q", got, d.expected)
		}
	}
}
