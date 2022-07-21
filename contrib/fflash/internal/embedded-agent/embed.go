// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package embeddedagent

import (
	_ "embed"
	"fmt"
)

const (
	ArchAarch64 = "aarch64"
	ArchX8664   = "x86_64"
)

//go:embed dut-agent-amd64.gz
var x8664Gzip []byte

//go:embed dut-agent-arm64.gz
var aarch64Gzip []byte

// ExecutableForArch returns the executable binary of dut-agent for the arch.
func ExecutableForArch(arch string) ([]byte, error) {
	switch arch {
	case ArchAarch64:
		return aarch64Gzip, nil
	case ArchX8664:
		return x8664Gzip, nil
	default:
		return nil, fmt.Errorf("unknown arch %q", arch)
	}
}
