// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

const labtunnelVersion = "2.0.0"

var (
	versionCmd = &cobra.Command{
		Use:   "version",
		Short: "Displays the version of labtunnel.",
		Args:  cobra.NoArgs,
		Run: func(cmd *cobra.Command, args []string) {
			fmt.Printf("labtunnel version: %s\n", labtunnelVersion)
		},
	}
)

func init() {
	rootCmd.AddCommand(versionCmd)
}
