// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"strconv"
	"time"

	"github.com/spf13/cobra"
)

var (
	btpeersCmdBtpeerCount = 1

	btpeersCmd = &cobra.Command{
		Use:   "btpeers <dut_hostname> [btpeer_count]",
		Short: "Ssh tunnel to dut and its bluetooth peers.",
		Long: `
Opens ssh tunnels to the dut and the remote chameleond port on its bluetooth
peers.

All tunnels are destroyed upon stopping labtunnel, and are restarted if
interrupted by a remote device reboot.

The dut tunnel is created in the same manner as with the dut command, run
"labtunnel dut --help" for details.

You can specify the number of bluetooth peers with the optional positional
argument "btpeer_count" after the dut hostname. The default is 1 btpeer.

The formula for the btpeer hostname is "<dut>-btpeer<n>", where "<dut>" is the
dut hostname (as used in the dut command) and "<n>" is the Nth bluetooth peer,
starting at 1.

When the --tauto flag is provided, btpeer tunnels are to the remote ssh port
rather than the remote chameleond port.
`,
		Args: func(cmd *cobra.Command, args []string) error {
			if len(args) != 1 && len(args) != 2 {
				return fmt.Errorf("requires 1 or 2 positional arguments, received %d", len(args))
			}
			if len(args) == 2 {
				var err error
				btpeersCmdBtpeerCount, err = strconv.Atoi(args[1])
				if err != nil || btpeersCmdBtpeerCount < 1 {
					return fmt.Errorf("btpeer_count must be a positive integer, got %q", args[1])
				}
			}
			return nil
		},
		Run: func(cmd *cobra.Command, args []string) {
			sshManager := buildSshManager()

			// Tunnel to dut.
			hostDut := resolveHostname(args[0], "")
			tunnelLocalPortToRemotePort(cmd.Context(), sshManager, "DUT", "", remotePortSsh, hostDut)

			// Tunnel to btpeers.
			tunnelToBtpeers(cmd.Context(), sshManager, hostDut, btpeersCmdBtpeerCount)

			time.Sleep(time.Second)
			sshManager.WaitUntilAllSshCompleted(cmd.Context())
		},
	}
)

func init() {
	rootCmd.AddCommand(btpeersCmd)
}
