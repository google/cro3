// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

//go:build with_embedded_agent

package embeddedagent

import (
	_ "embed"
	"fmt"
)

// SelfCheck returns an error if the embeddedagent was built incorrectly
func SelfCheck() error {
	return nil
}

//go:embed dut-agent-amd64.xz
var x8664Xzip []byte

//go:embed dut-agent-arm64.xz
var aarch64Xzip []byte

// ExecutableForArch returns the executable binary of dut-agent for the arch.
func ExecutableForArch(arch string) ([]byte, error) {
	switch arch {
	case ArchAarch64:
		return aarch64Xzip, nil
	case ArchX8664:
		return x8664Xzip, nil
	default:
		return nil, fmt.Errorf("unknown arch %q", arch)
	}
}
