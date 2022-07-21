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
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/progress"
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/ssh"
)

// BuilderPath is the parsed CHROMEOS_RELEASE_BUILDER_PATH on /etc/lsb-release
type BuilderPath struct {
	Board   string
	Release string
}

var _ fmt.Stringer = BuilderPath{}

func (r BuilderPath) String() string {
	return fmt.Sprintf("%s-release/%s", r.Board, r.Release)
}

var builderPathRegexp = regexp.MustCompile(`^([a-z]+)-\w+/(R[0-9-.]+)$`)
var builderPathLineRegexp = regexp.MustCompile(`CHROMEOS_RELEASE_BUILDER_PATH=(.+)\n`)

// DetectReleaseBuilder detects the release builder of c's remote host.
func DetectReleaseBuilder(c *ssh.Client) (BuilderPath, error) {
	stdout, err := c.RunSimpleOutput("cat /etc/lsb-release")
	if err != nil {
		return BuilderPath{}, err
	}

	match := builderPathLineRegexp.FindStringSubmatch(stdout)
	if match == nil {
		return BuilderPath{}, errors.New("cannot find CHROMEOS_RELEASE_BUILDER_PATH line")
	}
	path := match[1]

	match = builderPathRegexp.FindStringSubmatch(path)
	if match == nil {
		return BuilderPath{}, fmt.Errorf("cannot parse builder path: %s", path)
	}
	return BuilderPath{match[1], match[2]}, nil
}

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
	_, err = session.SimpleOutput("gzip -d > " + agentPath)
	if err != nil {
		return "", err
	}

	if _, err := c.RunSimpleOutput("chmod +x " + agentPath); err != nil {
		return "", err
	}

	return agentPath, nil
}
