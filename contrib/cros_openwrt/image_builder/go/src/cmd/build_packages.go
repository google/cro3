// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

var (
	buildPackageCmd = &cobra.Command{
		Use:          "build:packages",
		Short:        "Compiles custom OpenWrt packages.",
		Args:         cobra.NoArgs,
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			ib, err := NewCrosOpenWrtImageBuilder()
			if err != nil {
				return fmt.Errorf("failed to initialize CrosOpenWrtImageBuilder: %w", err)
			}
			if err := ib.CompileCustomPackages(cmd.Context()); err != nil {
				return fmt.Errorf("failed to compile custom OpenWrt packages: %w", err)
			}
			return nil
		},
	}
)

func init() {
	rootCmd.AddCommand(buildPackageCmd)
}
