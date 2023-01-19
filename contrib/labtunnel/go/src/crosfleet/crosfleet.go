// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crosfleet

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"os/exec"
	"time"
)

type leaseInfo struct {
	Leases []struct {
		Build struct {
			ID        string
			Status    string
			StartTime string
			Input     struct {
				Properties struct {
					LeaseLengthMinutes int `json:"lease_length_minutes"`
				}
			}
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
	leases, err := crosfleetGetLeases(ctx)
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

func crosfleetGetLeases(ctx context.Context) (*leaseInfo, error) {
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
	return leases, nil
}

// DUTLeaseTimeRemainingSeconds uses the given context calls crosfleet and then
// calculates the remaining time on the lease for the DUT identified by
// hostname.  Returns and int with time remaining (or 0 if lease has ended),
// and nil error if successful, otherwise returns 0 and an error if remaining
// lease time could not be determined.
func DUTLeaseTimeRemainingSeconds(ctx context.Context, hostname string) (int, error) {
	leases, err := crosfleetGetLeases(ctx)
	if err != nil {
		return 0, err
	}
	for _, lease := range leases.Leases {
		if lease.DUT.Hostname != hostname {
			continue
		}
		if lease.Build.Status != "STARTED" {
			return 0, nil
		}
		startTime, err := time.Parse(time.RFC3339, lease.Build.StartTime)
		if err != nil {
			return 0, fmt.Errorf("could not parse start time of lease: %w", err)
		}
		elapsed := time.Since(startTime).Seconds()
		remainingTime := int(math.Max(0, float64(lease.Build.Input.Properties.LeaseLengthMinutes*60)-elapsed))

		return remainingTime, nil
	}
	// no lease found so that must mean the DUT lease has expired
	return 0, nil
}
