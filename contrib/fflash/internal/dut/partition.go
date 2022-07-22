// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dut

import (
	"context"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/partitions"
)

func getActiveRootPartition(ctx context.Context) (string, error) {
	return runCommand(ctx, "rootdev", "-s")
}

func getActiveRootDevice(ctx context.Context) (string, error) {
	return runCommand(ctx, "rootdev", "-s", "-d")
}

func ActivePartitions(ctx context.Context) (partitions.State, error) {
	rootPart, err := getActiveRootPartition(ctx)
	if err != nil {
		return partitions.State{}, err
	}

	return partitions.GetStateFromRootPartition(rootPart)
}
