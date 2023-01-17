// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crosfleet

import (
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
)

type leaseInfo struct {
	Leases []struct {
		Build struct {
			ID     string
			Status string
		}
		DUT struct {
			Hostname string
		}
	}
}

func crosfleetInstalled() error {
	_, err := exec.LookPath("crosfleet")
	if err != nil {
		return fmt.Errorf("could not find crosfleet cli on path, goto http://go/crosfleet-cli for instructions to install it or specify a hostname for the DUT you would like to connect to.")
	}
	return nil
}

// CrosfleetLeasedDUTs will run the crosfleet cli and return a slice of strings
// for all DUTs that are actively leased by crosfleet.  Will return an error if
// crosfleet cli is not installed or there is a problem parsing JSON output
// from crosfleet.
func CrosfleetLeasedDUTs(ctx context.Context) ([]string, error) {
	if err := crosfleetInstalled(); err != nil {
		return nil, err
	}
	cmd := exec.CommandContext(ctx, "crosfleet", "dut", "leases", "-json")
	b, err := cmd.CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("could not get crosfleet lease info: %w", err)
	}
	leases, err := crosfleetParseLeases(b)
	if err != nil {
		return nil, err
	}
	var hostnames []string
	for _, lease := range leases.Leases {
		if lease.DUT.Hostname == "" {
			continue
		}
		// make sure we don't get inactive leasesq
		if lease.Build.Status != "STARTED" {
			continue
		}
		hostnames = append(hostnames, lease.DUT.Hostname)
	}
	return hostnames, nil
}

func crosfleetParseLeases(b []byte) (*leaseInfo, error) {
	var leases leaseInfo
	err := json.Unmarshal(b, &leases)
	if err != nil {
		return nil, fmt.Errorf("could not parse crosfleet lease info: %w", err)
	}
	return &leases, nil
}
