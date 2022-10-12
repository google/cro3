// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"time"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal"
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/logging"
)

func main() {
	t0 := time.Now()
	logging.SetUp(t0)
	log.SetPrefix("[fflash] ")

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()

	if err := internal.CLIMain(ctx, t0, os.Args[1:]); err != nil {
		log.Fatalln(err)
	}
}
