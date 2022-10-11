// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/alecthomas/kingpin"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal"
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/logging"
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/ssh"
)

const (
	statefulJunkFile = "/mnt/stateful_partition/junk"
	statefulJunkText = "JUNK"
)

func main() {
	ctx := context.Background()
	t0 := time.Now()
	logging.SetUp(t0)
	log.SetPrefix("[integration-test] ")

	var target string
	kingpin.Arg("dut-host", "the ssh target of the dut").Required().StringVar(&target)
	kingpin.Parse()

	if err := writeJunk(ctx, target); err != nil {
		log.Fatal("cannot write junk:", err)
	}
	if err := verifyJunk(ctx, target); err != nil {
		log.Fatal("failed to verify junk after writing:", err)
	}

	// Flash without clobbering.
	if err := internal.CLIMain(ctx, t0, []string{target}); err != nil {
		log.Fatal("non-clobbering flash failed:", err)
	}

	if err := verifyJunk(ctx, target); err != nil {
		log.Fatal("failed to verify junk after non-clobbering flash:", err)
	}

	// Flash again with clobber
	if err := internal.CLIMain(ctx, t0, []string{target, "--clobber-stateful=yes"}); err != nil {
		log.Fatal("clobbering flash failed:", err)
	}

	// Check that the junk file is removed after clobbering flash.
	cmd := ssh.DefaultCommand(ctx)
	cmd.Args = append(cmd.Args, target, "test", "!", "-e", statefulJunkFile)
	if err := cmd.Run(); err != nil {
		log.Fatal("junk file is not removed after clobbering flash")
	}

	log.Println("integration test complete")
}

// Write junk to the stateful partition.
func writeJunk(ctx context.Context, target string) error {
	cmd := ssh.DefaultCommand(ctx)
	cmd.Args = append(cmd.Args, target, "cat", ">", statefulJunkFile)
	cmd.Stdin = bytes.NewBufferString(statefulJunkText)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

func verifyJunk(ctx context.Context, target string) error {
	cmd := ssh.DefaultCommand(ctx)
	cmd.Args = append(cmd.Args, target, "cat", statefulJunkFile)
	cmd.Stderr = os.Stderr
	stdout, err := cmd.Output()
	if err != nil {
		return fmt.Errorf("failed to verify junk: %w", err)
	}

	if string(stdout) != statefulJunkText {
		return fmt.Errorf("junk file content %q did not match %q", string(stdout), statefulJunkText)
	}

	return nil
}
