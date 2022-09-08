// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"time"

	"github.com/spf13/cobra"
)

var (
	remotePortChameleondChameleon int

	chameleonCmd = &cobra.Command{
		Use:   "chameleon <dut_hostname>",
		Short: "Ssh tunnel to dut and its chameleon device.",
		Long: `
Opens ssh tunnels to dut and the remote chameleond port on its chameleon device.

All tunnels are destroyed upon stopping labtunnel, and are restarted if
interrupted by a remote device reboot.

The dut tunnel is created in the same manner as with the dut command, run
"labtunnel dut --help" for details.

The formula for the chameleon device hostname is "<dut>-chameleon".
`,
		Args: cobra.ExactArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			sshManager := buildSshManager()

			// Tunnel to dut.
			hostDut := resolveHostname(args[0], "")
			tunnelLocalPortToRemotePort(cmd.Context(), sshManager, "DUT", "", remotePortSsh, hostDut)

			// Tunnel to chameleon.
			hostChameleon := resolveHostname(hostDut, "-chameleon")
			tunnelLocalPortToRemotePort(cmd.Context(), sshManager, "CHAMELEON", "", remotePortChameleondChameleon, hostChameleon)

			time.Sleep(time.Second)
			sshManager.WaitUntilAllSshCompleted(cmd.Context())
		},
	}
)

func init() {
	rootCmd.AddCommand(chameleonCmd)
	chameleonCmd.Flags().IntVar(&remotePortChameleondChameleon, "remote-port-chameleond", 9992, "Remote port for accessing the chameleond service on chameleon devices")
}
