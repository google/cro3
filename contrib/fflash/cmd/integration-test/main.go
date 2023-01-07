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

	dialer, err := ssh.NewDialer(ssh.SshOptions{})
	if err != nil {
		log.Fatal("cannot create new ssh dialer:", err)
	}
	defer dialer.Close()

	if err := writeJunk(ctx, dialer, target); err != nil {
		log.Fatal("cannot write junk:", err)
	}
	if err := verifyJunk(ctx, dialer, target); err != nil {
		log.Fatal("failed to verify junk after writing:", err)
	}

	// Flash without clobbering, with rootfs verification.
	if err := internal.CLIMain(ctx, t0, []string{target, "--rootfs-verification=yes"}); err != nil {
		log.Fatal("non-clobbering flash failed:", err)
	}

	// Check rootfs verification is not disabled.
	if err := checkRootfsVerification(ctx, dialer, target, true); err != nil {
		log.Fatal("check for enabled rootfs verification failed: ", err)
	}

	// Check the junk file is still there.
	if err := verifyJunk(ctx, dialer, target); err != nil {
		log.Fatal("failed to verify junk after non-clobbering flash:", err)
	}

	// Flash again with clobber, without rootfs verification.
	if err := internal.CLIMain(ctx, t0, []string{target, "--clobber-stateful=yes"}); err != nil {
		log.Fatal("clobbering flash failed:", err)
	}

	// Check that the junk file is removed after clobbering flash.
	cmd := dialer.DefaultCommand(ctx)
	cmd.Args = append(cmd.Args, target, "test", "!", "-e", statefulJunkFile)
	if err := cmd.Run(); err != nil {
		log.Fatal("junk file is not removed after clobbering flash")
	}

	// Check rootfs verification is disabled.
	if err := checkRootfsVerification(ctx, dialer, target, false); err != nil {
		log.Fatal("check for disabled rootfs verification failed: ", err)
	}

	log.Println("integration test complete")
}

// Write junk to the stateful partition.
func writeJunk(ctx context.Context, dialer *ssh.Dialer, target string) error {
	cmd := dialer.DefaultCommand(ctx)
	cmd.Args = append(cmd.Args, target, "cat", ">", statefulJunkFile)
	cmd.Stdin = bytes.NewBufferString(statefulJunkText)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

func verifyJunk(ctx context.Context, dialer *ssh.Dialer, target string) error {
	cmd := dialer.DefaultCommand(ctx)
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

// checkRootfsVerification returns whether rootfs verification is in the desired state.
func checkRootfsVerification(ctx context.Context, dialer *ssh.Dialer, target string, enabled bool) error {
	cmd := dialer.DefaultCommand(ctx)
	cmd.Args = append(cmd.Args, target,
		// Check that rootfs verification is disabled.
		"/usr/libexec/debugd/helpers/dev_features_rootfs_verification", "-q",
	)
	if enabled {
		// Invert the exit status. Doing so in shell allows us to distinguish
		// ssh failures from dev_features_rootfs_verification returning non-zero.
		//
		// If dev_features_rootfs_verification fails, then exit 0 is executed.
		// If dev_features_rootfs_verification succeeds, then exit 0 is skipped, exit 1 is executed.
		cmd.Args = append(cmd.Args, "||", "exit", "0", "&&", "exit", "1")
	}

	return cmd.Run()
}
