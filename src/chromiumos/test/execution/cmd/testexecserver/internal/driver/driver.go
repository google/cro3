// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package driver implements test drivers for Tast and Autotest tests.
package driver

import (
	"context"

	"go.chromium.org/chromiumos/config/go/test/api"
)

// Type descript the type of drivers such as tast, tauto or others.
type Type int

const (
	// Unknown test driver.
	Unknown Type = iota
	// Tast test driver.
	Tast
	// Tauto test driver.
	Tauto
)

// Driver provides common interface to execute Tast and Autotest.
type Driver interface {
	// RunTests drives a test framework to execute tests.
	RunTests(ctx context.Context, resultsDir, dut, tlwAddr string, tests []string) (*api.RunTestsResponse, error)

	// Types returns the type of driver.
	Type() Type
}
