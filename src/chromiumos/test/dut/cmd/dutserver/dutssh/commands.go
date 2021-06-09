// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dutssh

import (
	"fmt"
	"strings"
)

// Formatters for commands

func PathExistsCommand(path string) string {
	return fmt.Sprintf("[ -e %s ] && echo -n 1 || echo -n 0", path)
}

func RunSerializerCommand(path string, chunkSize int64, fetchCore bool) string {
	command := []string{path, fmt.Sprintf("--chunk_size=%d", chunkSize)}
	if fetchCore {
		command = append(command, "--fetch_coredumps")
	}

	return strings.Join(command, " ")
}
