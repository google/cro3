// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

var (
	buildCmd = &cobra.Command{
		Use:          "build",
		Short:        "Compiles custom OpenWrt packages and builds a custom OpenWrt image.",
		Args:         cobra.NoArgs,
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			ib, err := NewCrosOpenWrtImageBuilder()
			if err != nil {
				return fmt.Errorf("failed to initilze CrosOpenWrtImageBuilder: %w", err)
			}
			if err := ib.CompileCustomPackages(cmd.Context()); err != nil {
				return fmt.Errorf("failed to compile custom OpenWrt packages: %w", err)
			}
			if err := ib.BuildCustomChromeOSTestImage(cmd.Context()); err != nil {
				return fmt.Errorf("failed to build custom OpenWrt image: %w", err)
			}
			return nil
		},
	}
)

func init() {
	rootCmd.AddCommand(buildCmd)
}
