// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package unit_tests

import (
	"chromiumos/test/local-cft/internal/utils"
	"testing"
)

func TestEnsureContainerAvailable_containerAvailable(t *testing.T) {
	desiredContainerName := "Container that definitely isn't running"

	if err := utils.EnsureContainerAvailable(desiredContainerName); err != nil {
		t.Fatalf("Container should have been available")
	}
}
