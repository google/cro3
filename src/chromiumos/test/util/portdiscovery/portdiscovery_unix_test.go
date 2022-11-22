// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

//go:build !windows
// +build !windows

package portdiscovery

import (
	"bytes"
	"os/exec"
	"strings"
	"testing"
)

func TestWriteMetadata_matchPort(t *testing.T) {
	t.Cleanup(cleanupMetaFile)
	meta := Metadata{Name: "cros-provision", Port: "8024", Version: "1.2"}
	util.WriteMetadata(meta)

	expect := "8024"
	stdout, stderr, err := printPort()
	if stderr != "" {
		t.Fatalf(stderr)
	}
	if err != nil {
		t.Fatalf(err.Error())
	}
	if stdout != expect {
		t.Fatalf("Result doesn't match\nexpect: %v\nactual: %v", expect, stdout)
	}
}

func TestWriteMetadata_append_matchNewPort(t *testing.T) {
	t.Cleanup(cleanupMetaFile)
	meta := Metadata{Name: "cros-provision", Port: "8024", Version: "1.2"}
	util.WriteMetadata(meta)
	meta = Metadata{Port: "8025"}
	util.WriteMetadata(meta)

	expect := "8025"
	stdout, stderr, err := printPort()
	if stderr != "" {
		t.Fatalf(stderr)
	}
	if err != nil {
		t.Fatalf(err.Error())
	}
	if stdout != expect {
		t.Fatalf("Result doesn't match\nexpect: %v\nactual: %v", expect, stdout)
	}
}

func printPort() (stdout string, stderr string, err error) {
	cmd := exec.Command("bash", "-c", "source ~/.cftmeta && echo $SERVICE_PORT")

	var se, so bytes.Buffer
	cmd.Stderr = &se
	cmd.Stdout = &so
	defer func() {
		stdout = strings.TrimSpace(so.String())
		stderr = strings.TrimSpace(se.String())
	}()

	err = cmd.Run()
	return
}
