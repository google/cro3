// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"time"

	"github.com/spf13/cobra"
)

var (
	remotePortChameleond int
	btPeerCount          int

	btPeersCmd = &cobra.Command{
		Use:   "btpeers <dut_hostname>",
		Short: "Ssh tunnel to bluetooth peers.",
		Long: `
Opens ssh tunnels to the remote chameleond port on bluetooth peers.

All tunnels are destroyed upon stopping labtunnel, and are restarted if
interrupted by a remote device reboot.

Specify the number of bluetooth peers to connect to with the --btpeers flag.

This does not create a tunnel for the dut, it just uses the provided dut
hostname to determine the hostnames of the btpeers. The formula for the btpeer
hostname is "<dut>-btpeer<n>", where "<dut>" is the dut hostname (as used in
the dut command) and "<n>" is the Nth bluetooth peer, starting at 1. If you need
tunnel to the dut, it's suggested to just run another labtunnel process using
the dut command.
`,
		Args: cobra.ExactArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			sshManager := buildSshManager()

			// Tunnel to btpeers.
			hostDut := resolveHostname(args[0], "")
			var localBluetoothPeers []string
			for i := 1; i <= btPeerCount; i++ {
				hostPeer := resolveHostname(hostDut, fmt.Sprintf("-btpeer%d", i))
				localPeer := tunnelLocalPortToRemotePort(cmd.Context(), sshManager, fmt.Sprint("BTPEER-", i), "", remotePortChameleond, hostPeer)
				localBluetoothPeers = append(localBluetoothPeers, localPeer)
			}

			time.Sleep(time.Second)
			sshManager.WaitUntilAllSshCompleted(cmd.Context())
		},
	}
)

func init() {
	rootCmd.AddCommand(btPeersCmd)
	btPeersCmd.Flags().IntVar(&btPeerCount, "btpeers", 1, "Number of btpeers in wificell to tunnel to (-btpeer1, -btpeer2, ...)")
	btPeersCmd.Flags().IntVar(&remotePortChameleond, "remote-port-chameleond", 9992, "Remote port for accessing the chameleond service on btpeers")
}
