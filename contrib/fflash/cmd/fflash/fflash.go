// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"strconv"
	"time"

	"github.com/alecthomas/kingpin"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal"
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/logging"
)

func init() {
}

func main() {
	t0 := time.Now()
	logging.SetUp(t0)
	log.SetPrefix("[fflash] ")

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()

	target := kingpin.Arg("dut-host", "the ssh target of the dut").Required().String()
	var opts internal.Options
	kingpin.Flag("gs", "gs:// directory to flash. Use with caution!").StringVar(&opts.GS)
	kingpin.Flag("R", "release number. ex: 105 or 105-14989.0.0").Short('R').StringVar(&opts.ReleaseString)
	kingpin.Flag("board",
		"flash from gs://chromeos-image-archive/${board}-release/R*. Use with caution!").
		StringVar(&opts.Board)
	kingpin.Parse()

	r, err := strconv.Atoi(opts.ReleaseString)
	if err == nil {
		opts.ReleaseNum = r
		opts.ReleaseString = ""
	}

	if err := internal.Main(ctx, t0, *target, &opts); err != nil {
		log.Fatalln(err)
	}

	log.Println("DUT flashed successfully")
}
