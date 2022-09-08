// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dutssh

import (
	"fmt"
	"strings"
)

type CmdResult struct {
	ReturnCode int32
	StdOut     string
	StdErr     string
}

// Simple interface abstracting away many details around SSH/streaming for
// clients that execute many simple/quick commands.
// This insulate clients from the full complexity of DutServer and also
// makes it easier to test logic that's focused on command execution results.
// E.g. Identity scanning
type CmdExecutor interface {
	RunCmd(cmd string) (*CmdResult, error)
}

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
