// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"

	"github.com/spf13/cobra"
)

var (
	rootCmd = &cobra.Command{
		Use:     "labtunnel",
		Version: "2.3.0",
		Short:   "Create and maintain ssh tunnels for common lab environments easily.",
		Long: `
Create and maintain ssh tunnels for common lab environments easily.

To stop a running labtunnel command, send the SIGINT signal to the process. If
running labtunnel in a terminal environment, you can do this with CTRL+C.

All hosts that are accessed or tunneled through with any labtunnel command must
be configured so that they can be accessed without a username or password
prompt. This can be done securely by configuring your system's ssh settings to
use private keys for the given host. Temporary/test ssh configurations can also
be done directly with labtunnel with the "-o" flag to pass ssh config options
to the ssh command calls.

All tunnels are destroyed upon stopping labtunnel, and are restarted if
interrupted by a remote device reboot.

When a local port is forwarded to remote port, the next available port starting
at 2200 is used. The start port can be adjusted with --local-port-start. Used
ports will be freed upon stopping labtunnel.
`,
	}

	// Persistent CLI Flags.
	localPortStart       int
	sshOptions           []string
	remotePortSsh        int
	sshRetryDelaySeconds int
	remotePortChameleond int
	forAutotest          bool
)

func init() {
	rootCmd.PersistentFlags().IntVarP(&localPortStart, "local-port-start", "p", 2200, "Initial local port to forward to tunnel")
	rootCmd.PersistentFlags().IntVar(&remotePortSsh, "remote-port-ssh", 22, "Remote port to forward ssh tunnels to")
	rootCmd.PersistentFlags().IntVar(&sshRetryDelaySeconds, "ssh-retry-delay-seconds", 10, "Time to wait before retrying failed ssh command calls")
	rootCmd.PersistentFlags().StringSliceVarP(
		&sshOptions, "ssh-options", "o",
		[]string{
			"StrictHostKeyChecking=no",
			"ExitOnForwardFailure=yes",
			"ForkAfterAuthentication=no",
			"LogLevel=ERROR",
			"ControlMaster=auto",
			"ControlPersist=3600",
			"ControlPath=/tmp/ssh-labtunnel-%C",
			"ServerAliveCountMax=10",
			"ServerAliveInterval=1",
			"VerifyHostKeyDNS=no",
			"CheckHostIP=no",
			"UserKnownHostsFile=/dev/null",
			"Compression=yes",
		},
		"ssh options for all ssh commands",
	)
	rootCmd.PersistentFlags().IntVar(&remotePortChameleond, "remote-port-chameleond", 9992, "Remote port for accessing the chameleond service on btpeers and chameleon devices")
	rootCmd.PersistentFlags().BoolVarP(&forAutotest, "tauto", "a", false, "For tunnel usage that differs between Tauto/Autotest and Tast, make then as expected for Tauto (effects btpeer and chameleon tunnels)")
}

func Execute(ctx context.Context) error {
	return rootCmd.ExecuteContext(ctx)
}
