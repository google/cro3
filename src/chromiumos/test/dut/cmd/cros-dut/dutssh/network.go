// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dutssh

import (
	"context"
	"fmt"
	"time"

	"go.chromium.org/chromiumos/config/go/api/test/tls"
	"golang.org/x/crypto/ssh"
	"google.golang.org/grpc"
)

// GetSSHAddr returns the SSH address to use for the DUT, through the wiring service.
func GetSSHAddr(ctx context.Context, name string, wiringAddress string) (string, error) {
	c, err := createWiringClient(wiringAddress)
	if err != nil {
		return "", err
	}
	resp, err := c.OpenDutPort(ctx, &tls.OpenDutPortRequest{
		Name: name,
		Port: 22,
	})
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("%s:%d", resp.GetAddress(), resp.GetPort()), nil
}

// GetSSHConfig construct a static ssh config
func GetSSHConfig() *ssh.ClientConfig {
	return &ssh.ClientConfig{
		User: "root",
		// We don't care about the host key for DUTs.
		// Attackers intercepting our connections to DUTs is not part
		// of our attack profile.
		HostKeyCallback: ssh.InsecureIgnoreHostKey(),
		Timeout:         5 * time.Second,
		// Use the well known testing RSA key as the default SSH auth
		// method.
		Auth: []ssh.AuthMethod{ssh.PublicKeys(testingSSHSigner)},
	}
}

// createWiringClient creates a client to wiring service
func createWiringClient(wiringAddress string) (tls.WiringClient, error) {
	conn, err := grpc.Dial(wiringAddress, grpc.WithInsecure())
	if err != nil {
		return nil, err
	}
	return tls.WiringClient(tls.NewWiringClient(conn)), nil
}
