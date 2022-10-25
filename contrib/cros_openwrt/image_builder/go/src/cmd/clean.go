// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"os"

	"chromiumos/platform/dev/contrib/cros_openwrt/image_builder/dirs"
	"github.com/spf13/cobra"
)

var (
	cleanAll bool

	cleanCmd = &cobra.Command{
		Use:          "clean",
		Short:        "Deletes temporary files.",
		Args:         cobra.NoArgs,
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			if _, err := os.Stat(workingDirPath); os.IsNotExist(err) {
				return fmt.Errorf("working directory %q does not exist", workingDirPath)
			}
			wd, err := dirs.NewWorkingDirectory(workingDirPath)
			if err != nil {
				return fmt.Errorf("failed to initialize working directory at %q: %w", workingDirPath, err)
			}
			if cleanAll {
				if err := wd.CleanAll(); err != nil {
					return fmt.Errorf("failed to fully remove working directory at %q: %w", workingDirPath, err)
				}
			} else {
				if err := wd.CleanIntermediaryFiles(); err != nil {
					return fmt.Errorf("failed to remove intermediary files from working directory at %q: %w", workingDirPath, err)
				}
			}
			return nil
		},
	}
)

func init() {
	cleanCmd.Flags().BoolVar(
		&cleanAll,
		"all",
		false,
		"Fully delete working directory (sdk and image builder downloads, intermediary files, built packages, built images)",
	)

	rootCmd.AddCommand(cleanCmd)
}
