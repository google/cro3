// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"log"
	"os"
	"time"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal"
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/logging"
)

func init() {
}

func main() {
	t0 := time.Now()
	logging.SetUp(t0)
	log.SetPrefix("[fflash] ")

	ctx := context.TODO()

	if err := internal.Main(ctx, t0, os.Args[1]); err != nil {
		log.Fatalln(err)
	}

	log.Println("flash complete, please reboot DUT manually.")
}
