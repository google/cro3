// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"errors"
	"time"

	"github.com/spf13/cobra"
)

var (
	hostsDut        []string
	hostsRouter     []string
	hostsPcap       []string
	hostsBtpeer     []string
	hostsChameleon  []string
	hostsSsh        []string
	hostsChameleond []string

	hostsCmd = &cobra.Command{
		Use:   "hosts",
		Short: "Tunnel to different types of hosts without any automatic hostname resolution.",
		Long: `
Tunnel to different types of hosts without any automatic hostname resolution.

To specify a host, use one of the flags with a given hostname and a tunnel will
be created to that host as expected for that type of host. Multiple hosts
can be tunneled to at the same time, even for the same type, by providing
multiple flags (see example calls below).

Hostnames provided will be the exact hostnames passed to the ssh command call,
and can be IP addresses. Tunnels will only be created for the hosts specified.

Example calls:
$ labtunnel hosts --dut <dut_host>
$ labtunnel hosts --dut <dut1_host> --dut <dut2_host>
$ labtunnel hosts --dut <dut_host> --router <router_host> --pcap <pcap_host>
$ labtunnel hosts --dut <dut_host> --btpeer <btpeer1_host> --btpeer <btpeer2_host>
$ labtunnel hosts --dut <dut_host> --chameleon <chameleon_host>
$ labtunnel hosts --ssh <host>
$ labtunnel hosts --chameleond <host>
`,
		Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			sshManager := buildSshManager()

			// Tunnel to the specified hosts.
			tunnelCount := 0
			for i, host := range hostsDut {
				tunnelToDut(cmd.Context(), sshManager, i+1, host)
				tunnelCount++
			}
			for i, host := range hostsRouter {
				tunnelToRouter(cmd.Context(), sshManager, i+1, host)
				tunnelCount++
			}
			for i, host := range hostsPcap {
				tunnelToPcap(cmd.Context(), sshManager, i+1, host)
				tunnelCount++
			}
			for i, host := range hostsBtpeer {
				tunnelToBtpeer(cmd.Context(), sshManager, i+1, host)
				tunnelCount++
			}
			for i, host := range hostsChameleon {
				tunnelToChameleon(cmd.Context(), sshManager, i+1, host)
				tunnelCount++
			}
			for i, host := range hostsSsh {
				genericTunnelToSshPort(cmd.Context(), sshManager, i+1, host)
				tunnelCount++
			}
			for i, host := range hostsChameleond {
				genericTunnelToChameleondPort(cmd.Context(), sshManager, i+1, host)
				tunnelCount++
			}

			if tunnelCount == 0 {
				return errors.New("no hosts specified to tunnel to")
			}

			time.Sleep(time.Second)
			sshManager.WaitUntilAllSshCompleted(cmd.Context())
			return nil
		},
	}
)

func init() {
	rootCmd.AddCommand(hostsCmd)
	hostsCmd.Flags().StringArrayVar(&hostsDut, "dut", []string{}, "Dut hosts to tunnel to")
	hostsCmd.Flags().StringArrayVar(&hostsRouter, "router", []string{}, "Router hosts to tunnel to")
	hostsCmd.Flags().StringArrayVar(&hostsPcap, "pcap", []string{}, "Pcap hosts to tunnel to")
	hostsCmd.Flags().StringArrayVar(&hostsBtpeer, "btpeer", []string{}, "Btpeer hosts to tunnel to")
	hostsCmd.Flags().StringArrayVar(&hostsChameleon, "chameleon", []string{}, "Chameleon hosts to tunnel to")
	hostsCmd.Flags().StringArrayVar(&hostsSsh, "ssh", []string{}, "Hosts to tunnel to their ssh port")
	hostsCmd.Flags().StringArrayVar(&hostsChameleond, "chameleond", []string{}, "Hosts to tunnel to their chameleond port")
}
