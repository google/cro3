// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package device implements utilities to extract device information.
package device

import (
	"errors"
	"fmt"
	"net"
	"strconv"

	"go.chromium.org/chromiumos/config/go/test/api"
	labapi "go.chromium.org/chromiumos/config/go/test/lab/api"
)

// DutInfo stores
type DutInfo struct {
	Addr            string // The address of the DUT.
	Role            string // The role of the DUT.
	Servo           string // The address of the servo.
	DutServer       string // The address of the dutServer.
	ProvisionServer string // address of the provision server
}

// joinHostAndPort joins host and port to a single address.
// Example 1: "127.0.0.1" "" -> "127.0.0.1".
// Example 2: "0:0:0:0:0:ffff:7f00:1" "2" -> "[0:0:0:0:0:ffff:7f00:1]:2".
// Example 3: "0:0:0:0:0:ffff:7f00:1" "" -> 0:0:0:0:0:ffff:7f00:1"
func joinHostAndPort(endpoint *labapi.IpEndpoint) string {
	if endpoint.Port == 0 {
		return endpoint.Address
	}
	return net.JoinHostPort(endpoint.Address, strconv.Itoa(int(endpoint.Port)))
}

// Address returns the address of a DUT.
// TODO: Remove this after no test drivers are using this.
func Address(device *api.CrosTestRequest_Device) (string, error) {
	if device == nil {
		return "", errors.New("requested device is nil")
	}
	dut := device.Dut
	if dut == nil {
		return "", errors.New("DUT is nil")
	}
	chromeOS := dut.GetChromeos()
	if chromeOS == nil {
		return "", fmt.Errorf("DUT does not have end point information: %v", dut)
	}
	return joinHostAndPort(chromeOS.Ssh), nil

}

// FillDUTInfo extraction DUT information from a device.
func FillDUTInfo(device *api.CrosTestRequest_Device, role string) (*DutInfo, error) {
	if device == nil {
		return nil, errors.New("requested device is nil")
	}
	dut := device.Dut
	if dut == nil {
		return nil, errors.New("DUT is nil")
	}
	chromeOS := dut.GetChromeos()
	if chromeOS == nil {
		return nil, fmt.Errorf("DUT does not have end point information: %v", dut)
	}
	addr := joinHostAndPort(chromeOS.Ssh)

	// Servo address.
	var servo string
	if chromeOS.Servo != nil && chromeOS.Servo.ServodAddress != nil {
		servo = joinHostAndPort(chromeOS.Servo.ServodAddress)
	}

	// DUT Server address.
	var dutServer string
	if device.DutServer != nil {
		dutServer = joinHostAndPort(device.DutServer)
	}
	// Provision server address.
	var provisionServer string
	if device.ProvisionServer != nil {
		provisionServer = joinHostAndPort(device.ProvisionServer)
	}

	return &DutInfo{
		Addr:            addr,
		Role:            role,
		Servo:           servo,
		DutServer:       dutServer,
		ProvisionServer: provisionServer,
	}, nil
}
