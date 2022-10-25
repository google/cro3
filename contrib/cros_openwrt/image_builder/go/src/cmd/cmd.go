// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"strings"

	"chromiumos/platform/dev/contrib/cros_openwrt/image_builder/fileutils"
)

func Execute(ctx context.Context) error {
	return rootCmd.ExecuteContext(ctx)
}

func promptYesNo(ctx context.Context, message string, defaultAnswer bool) (bool, error) {
	if defaultAnswer {
		message += " (Y/n):"
	} else {
		message += " (y/N):"
	}
	response, err := contextualPrompt(ctx, message)
	if err != nil {
		return defaultAnswer, err
	}
	response = strings.TrimSpace(response)
	if response == "" {
		return defaultAnswer, nil
	}
	response = strings.ToLower(response)
	return response == "y", nil
}

func contextualPrompt(ctx context.Context, message string) (string, error) {
	fmt.Printf("\n%s ", message)
	inputReader := bufio.NewReader(fileutils.NewContextualReaderWrapper(ctx, os.Stdin))
	input, err := inputReader.ReadString('\n')
	if err != nil {
		return "", fmt.Errorf("failed to read user input for prompt: %w", err)
	}
	fmt.Println()
	return input, nil
}
