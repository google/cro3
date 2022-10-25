// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main includes the main function for running
// cros_openwrt_image_builder as an executable.
package main

import (
	"context"
	"os"
	"os/signal"

	"chromiumos/platform/dev/contrib/cros_openwrt/image_builder/cmd"
	"chromiumos/platform/dev/contrib/cros_openwrt/image_builder/log"
)

func main() {
	// Create context that will cancel when a SIGINT signal is received.
	ctx, cancel := context.WithCancel(context.Background())
	interruptSignalChannel := make(chan os.Signal, 1)
	signal.Notify(interruptSignalChannel, os.Interrupt)
	defer func() {
		signal.Stop(interruptSignalChannel)
		cancel()
	}()
	go func() {
		select {
		case <-interruptSignalChannel:
			log.Logger.Println("received SIGINT, cancelling operations")
			cancel()
		case <-ctx.Done():
		}
	}()

	// Run the command.
	_ = cmd.Execute(ctx)
}
