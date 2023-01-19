// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"time"

	"chromiumos/platform/dev/contrib/labtunnel/log"

	"github.com/spf13/cobra"
)

var (
	remotePortCallbox        int
	remotePortCallboxManager int

	callboxCmd = &cobra.Command{
		Use:   "callbox <dut_hostname> <callbox_proxy_hostname> <remote_callbox_hostname>",
		Short: "Ssh tunnel to dut, callbox manager, and callbox.",
		Long: `
Opens ssh tunnels for dut ssh, the callbox manager service on a proxy host, and
the specified callbox through the proxy host.

All tunnels are destroyed upon stopping labtunnel, and are restarted if
interrupted by a remote device reboot.

The dut tunnel is created in the same manner as with the dut command, run
"labtunnel dut --help" for details.

The callbox manager tunnel is made to
"<callbox_proxy_hostname>:<remote-port-callbox-manager>".

The callbox tunnel is made to "<remote_callbox_hostname>:<remote-port-callbox>"
on the proxy host, as the callboxes do not support SSH.
`,
		Args: cobra.ExactArgs(3),
		RunE: func(cmd *cobra.Command, args []string) error {
			sshManager := buildSshManager()

			// Tunnel to dut.
			hostDut, leased, err := resolveDutHostname(cmd.Context(), args[0])
			if err != nil {
				return fmt.Errorf("could not determine hostname: %w", err)
			}
			localDut := tunnelToDut(cmd.Context(), sshManager, 1, hostDut)

			// Tunnel to Callbox Manager service on callbox proxy.
			hostProxy := args[1]
			localCallboxManager := tunnelLocalPortToRemotePort(cmd.Context(), sshManager, "CALLBOX_MANAGER", "", remotePortCallboxManager, hostProxy)

			// Tunnel to callbox through proxy.
			hostCallbox := args[2]
			localCallbox := tunnelLocalPortToRemotePort(cmd.Context(), sshManager, "CALLBOX", hostCallbox, remotePortCallbox, hostProxy)

			time.Sleep(time.Second)
			log.Logger.Printf(
				"Example Tast call (in chroot): tast run -var=callbox=%s -var=callboxManager=%s %s <test>",
				localCallbox,
				localCallboxManager,
				localDut)
			ctx := cmd.Context()
			if leased {
				ctx = pollDUTLease(ctx, hostDut)
			}
			sshManager.WaitUntilAllSshCompleted(ctx)
			return nil
		},
	}
)

func init() {
	rootCmd.AddCommand(callboxCmd)
	callboxCmd.Flags().IntVar(&remotePortCallbox, "remote-port-callbox", 5025, "Remote port for accessing callboxes directly")
	callboxCmd.Flags().IntVar(&remotePortCallboxManager, "remote-port-callbox-manager", 5000, "Remote port for accessing the callbox manager service")
}
