// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"strings"
	"time"

	"github.com/spf13/cobra"

	"chromiumos/platform/dev/contrib/labtunnel/log"
)

var (
	pcapCount              int
	routerCount            int
	wificellCmdBtpeerCount int

	wificellCmd = &cobra.Command{
		Use:   "wificell <dut_hostname>",
		Short: "Ssh tunnel to the dut, pcap, and router of a wificell.",
		Long: `
Opens an ssh tunnel to the remote ssh port to the dut, pcap, and router of a
wificell.

All tunnels are destroyed upon stopping labtunnel, and are restarted if
interrupted by a remote device reboot.

The dut tunnel is created in the same manner as with the dut command, run
"labtunnel dut --help" for details.

The router hostname is dut hostname plus the "-router" suffix. The pcap hostname
is dut hostname plus the "-pcap" suffix. If the --routers or --pcaps flag value
is set to 0, then no tunnels will be created for the respective device type. If
the dut hostname ends with ".cros", the router and pcap hostnames generated
from the dut hostname will still end with ".cros" (e.g. "-router.cros").

The btpeer tunnels are created in the same manner as with the btpeers command,
see "labtunnel btpeers --help" for details.
`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			sshManager := buildSshManager()

			// Tunnel to dut.
			hostDut, err := resolveDutHostname(cmd.Context(), args[0])
			if err != nil {
				return fmt.Errorf("could not determine hostname: %w", err)
			}
			localDut := tunnelToDut(cmd.Context(), sshManager, 1, hostDut)

			// Tunnel to routers.
			localRouters := tunnelToRoutersUsingDutHost(cmd.Context(), sshManager, hostDut, routerCount)

			// Tunnel to pcaps.
			localPcaps := tunnelToPcapsUsingDutHost(cmd.Context(), sshManager, hostDut, pcapCount)

			// Tunnel to btpeers.
			tunnelToBtpeersUsingDutHost(cmd.Context(), sshManager, hostDut, wificellCmdBtpeerCount)

			time.Sleep(time.Second)
			log.Logger.Printf(
				"Example Tast call (in chroot): tast run -var=router=%s -var=pcap=%s %s <test>",
				strings.Join(localRouters, ","),
				strings.Join(localPcaps, ","),
				localDut)
			sshManager.WaitUntilAllSshCompleted(cmd.Context())
			return nil
		},
	}
)

func init() {
	rootCmd.AddCommand(wificellCmd)
	wificellCmd.Flags().IntVar(&routerCount, "routers", 1, "Number of routers in wificell to tunnel to (-router, -router2, -router3, ...)")
	wificellCmd.Flags().IntVar(&pcapCount, "pcaps", 1, "Number of pcap devices in wificell to tunnel to (-pcap, -pcap2, -pcap3, ...)")
	wificellCmd.Flags().IntVar(&wificellCmdBtpeerCount, "btpeers", 0, "Number of btpeers in wificell to tunnel to (-btpeer1, -btpeer2, ...)")
}
