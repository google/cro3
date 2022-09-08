// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"strconv"
	"time"

	"github.com/spf13/cobra"
)

var (
	sshWatcherCmd = &cobra.Command{
		Use:   "sshwatcher host1 [host2 [... hostN]]",
		Short: "Ssh tunnel to host(s).",
		Long: `
Opens an ssh tunnel to the remote ssh port to specified host(s).

All tunnels are destroyed upon stopping labtunnel, and are restarted if
interrupted by a remote device reboot.

This is command is comparable to the independent "sshwatcher" utility, which
does the same thing. In this version, the local forwarded port does not have
to be specified and is selected like it is for other tunnels in labtunnel. See
"labtunnel --help" for more details on port selection.
`,
		Args: cobra.MinimumNArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			sshManager := buildSshManager()

			// Tunnel to the specified hosts.
			for i, host := range args {
				tunnelLocalPortToRemotePort(cmd.Context(), sshManager, strconv.Itoa(i+1), "", remotePortSsh, host)
			}

			time.Sleep(time.Second)
			sshManager.WaitUntilAllSshCompleted(cmd.Context())
		},
	}
)

func init() {
	rootCmd.AddCommand(sshWatcherCmd)
}
