// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"time"

	"chromiumos/platform/dev/contrib/labtunnel/log"
	"chromiumos/platform/dev/contrib/labtunnel/ssh"

	"github.com/spf13/cobra"
)

const remoteVncCmd = "kmsvnc"
const tigerVncCmd = "xtigervncviewer"

var (
	doNotOpenVnc  bool
	remotePortVnc int

	dutVncCmd = &cobra.Command{
		Use:   "dutvnc <dut_hostname>",
		Short: "Starts and connects to a VNC server on dut for remote GUI access.",
		Long: `
Starts kmsvnc on the dut via ssh, opens a tunnel to it, and connects to it using
TigerVNC.

The dut tunnel is created in the same manner as with the dut command, run
"labtunnel dut --help" for details.

The kmsvnc process on the dut and TigerVNC client on this machine are stopped
and all tunnels are destroyed upon stopping labtunnel.

To use a different VNC client other than TigerVNC, use the --do-not-open-vnc
option to skip connecting to the VNC server with TigerVNC and then connect to
localhost:5900 with your preferred VNC client.
`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			sshManager := buildSshManager()
			hostDut, leased, err := resolveDutHostname(cmd.Context(), args[0])
			if err != nil {
				return fmt.Errorf("could not determine hostname: %w", err)
			}

			// Launch kmsvnc on dut.
			sshManager.Ssh(cmd.Context(), true, "DUT-VNC", func(ctx context.Context, r *ssh.Runner) error {
				return r.Run(ctx, nil, []string{
					hostDut,
					remoteVncCmd,
				})
			})

			// Tunnel to kmsvnc port on dut.
			localVnc := tunnelLocalPortToRemotePort(cmd.Context(), sshManager, "DUT-VNC", "", remotePortVnc, hostDut)

			log.Logger.Println("DUT VNC available at", localVnc)

			if !doNotOpenVnc {
				// Wait a moment and then launch TigerVNC.
				time.Sleep(5 * time.Second)
				go func() {
					runContextualCommand(cmd.Context(), "TIGERVNC: ", tigerVncCmd, localVnc, "-Log", "*:stderr:0")
				}()
			}

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
	rootCmd.AddCommand(dutVncCmd)
	dutVncCmd.Flags().BoolVar(&doNotOpenVnc, "do-not-open-vnc", false, "Do not launch TigerVNC")
	dutVncCmd.Flags().IntVar(&remotePortVnc, "remote-port-vnc", 5900, "Remote port for accessing kmsvnc on the dut")
}
