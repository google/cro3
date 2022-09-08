// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

//go:build !with_embedded_agent

package embeddedagent

import (
	"errors"
)

var err error = errors.New("fflash was built incorrectly, embedded dut-agent is not available")

// SelfCheck returns an error if the embeddedagent was built incorrectly
func SelfCheck() error {
	return err
}

// ExecutableForArch returns the executable binary of dut-agent for the arch.
func ExecutableForArch(arch string) ([]byte, error) {
	return nil, err
}
