// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"path"
	"regexp"
	"strings"

	embeddedagent "chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/embedded-agent"
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/partitions"
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/progress"
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/ssh"
)

var boardLineRegexp = regexp.MustCompile(`CHROMEOS_RELEASE_BOARD=(.+)\n`)

// DetectBoard detects the board of c's remote host.
func DetectBoard(c *ssh.Client) (string, error) {
	stdout, err := c.RunSimpleOutput("cat /etc/lsb-release")
	if err != nil {
		return "", err
	}

	match := boardLineRegexp.FindStringSubmatch(stdout)
	if match == nil {
		return "", errors.New("cannot find CHROMEOS_RELEASE_BOARD line")
	}

	return match[1], err
}

// DetectPartitions detects the active/inactive partition state on c's remote host.
func DetectPartitions(c *ssh.Client) (partitions.State, error) {
	rootPart, err := c.RunSimpleOutput("rootdev -s")
	if err != nil {
		return partitions.State{}, err
	}

	return partitions.GetStateFromRootPartition(strings.TrimSuffix(rootPart, "\n"))
}

// DetectArch detects the CPU architecture on c's remote host.
func DetectArch(c *ssh.Client) (string, error) {
	stdout, err := c.RunSimpleOutput("uname -m")
	if err != nil {
		return "", err
	}
	arch := strings.TrimSuffix(stdout, "\n")
	switch arch {
	case embeddedagent.ArchAarch64, embeddedagent.ArchX8664:
		return arch, nil
	default:
		return "", fmt.Errorf("unknown arch %q", arch)
	}
}

// PushCompressedExecutable pushes a compressed executable to c's remote host.
// The path of the pushed executable is returned.
func PushCompressedExecutable(ctx context.Context, c *ssh.Client, b []byte) (string, error) {
	if _, err := c.RunSimpleOutput("mount -o remount,exec /tmp"); err != nil {
		return "", err
	}

	tempDir, err := c.RunSimpleOutput("mktemp --directory --tmpdir=/tmp dut-agent.XXXXXXXXXX")
	if err != nil {
		return "", err
	}
	tempDir = strings.TrimSuffix(tempDir, "\n")
	agentPath := path.Join(tempDir, "dut-agent")

	if _, err := c.RunSimpleOutput("mount -t tmpfs -o rw,exec,mode=700 dut-agent " + tempDir); err != nil {
		panic(err)
	}

	session, err := c.NewSession()
	if err != nil {
		return "", err
	}
	defer session.Close()
	prog := progress.NewWriter("push", int64(len(b)))
	defer prog.Close()
	session.Stdin = io.TeeReader(bytes.NewBuffer(b), prog)
	_, err = session.SimpleOutput("xz -d > " + agentPath)
	if err != nil {
		return "", err
	}

	if _, err := c.RunSimpleOutput("chmod +x " + agentPath); err != nil {
		return "", err
	}

	return agentPath, nil
}
