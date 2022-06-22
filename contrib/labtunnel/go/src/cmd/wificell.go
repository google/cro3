// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"strings"
	"time"

	"chromiumos/platform/dev/contrib/labtunnel/log"
	"github.com/spf13/cobra"
)

var (
	pcapCount   int
	routerCount int

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
`,
		Args: cobra.ExactArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			sshManager := buildSshManager()

			// Tunnel to dut.
			hostDut := resolveHostname(args[0], "")
			localDut := tunnelLocalPortToRemotePort(cmd.Context(), sshManager, "DUT", "", remotePortSsh, hostDut)

			// Tunnel to routers.
			var localRouters []string
			for i := 1; i <= routerCount; i++ {
				suffix := "-router"
				if i != 1 {
					suffix = fmt.Sprintf("%s%d", suffix, i)
				}
				hostRouter := resolveHostname(hostDut, suffix)
				localRouter := tunnelLocalPortToRemotePort(cmd.Context(), sshManager, fmt.Sprint("ROUTER-", i), "", remotePortSsh, hostRouter)
				localRouters = append(localRouters, localRouter)
			}

			// Tunnel to pcaps.
			var localPcaps []string
			for i := 1; i <= pcapCount; i++ {
				suffix := "-pcap"
				if i != 1 {
					suffix = fmt.Sprintf("%s%d", suffix, i)
				}
				hostPcap := resolveHostname(hostDut, suffix)
				localPcap := tunnelLocalPortToRemotePort(cmd.Context(), sshManager, fmt.Sprint("PCAP-", i), "", remotePortSsh, hostPcap)
				localPcaps = append(localPcaps, localPcap)
			}

			time.Sleep(time.Second)
			log.Logger.Printf(
				"Example Tast call (in chroot): tast run -var=router=%s -var=pcap=%s %s <test>",
				strings.Join(localRouters, ","),
				strings.Join(localPcaps, ","),
				localDut)
			sshManager.WaitUntilAllSshCompleted(cmd.Context())
		},
	}
)

func init() {
	rootCmd.AddCommand(wificellCmd)
	wificellCmd.Flags().IntVar(&routerCount, "routers", 1, "Number of routers in wificell to tunnel to (-router, -router2, -router3, ...)")
	wificellCmd.Flags().IntVar(&pcapCount, "pcaps", 1, "Number of pcap devices in wificell to tunnel to (-pcap, -pcap2, -pcap3, ...)")
}
