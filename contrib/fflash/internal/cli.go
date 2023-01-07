// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"context"
	"fmt"
	"log"
	"strconv"
	"time"

	"github.com/alecthomas/kingpin"
)

func cliParse(args []string) (target string, opts Options, err error) {
	const (
		yes  = "yes"
		no   = "no"
		auto = "auto"
	)

	app := kingpin.New("fflash", "")
	app.Arg("dut-host", "the ssh target of the dut").Required().StringVar(&target)
	app.Flag("gs", "gs:// directory to flash. Use with caution!").StringVar(&opts.GS)
	app.Flag("R", "release number. ex: 105 or 105-14989.0.0").Short('R').StringVar(&opts.ReleaseString)
	app.Flag("board",
		"flash from gs://chromeos-image-archive/${board}-release/R*. Use with caution!").
		StringVar(&opts.Board)
	app.Flag("port", "port number to connect to on the dut-host").Short('p').StringVar(&opts.Port)
	rootfsVerification := app.Flag(
		"rootfs-verification",
		"whether rootfs verification on the new root is enabled. "+
			"Choices: yes, no (default)",
	).Default(no).Enum(yes, no)
	clobberStateful := app.Flag(
		"clobber-stateful",
		"whether to clobber the stateful partition. Choices: yes, no (default)").Default(no).Enum(yes, no)
	clearTpmOwner := app.Flag(
		"clear-tpm-owner",
		"whether to clear the TPM owner on reboot. "+
			" Choices: yes, no, auto (default, follows --clobber-stateful)",
	).Default(auto).Enum(auto, yes, no)

	if _, err := app.Parse(args); err != nil {
		return target, opts, fmt.Errorf("error: %w, try --help", err)
	}

	r, err := strconv.Atoi(opts.ReleaseString)
	if err == nil {
		opts.ReleaseNum = r
		opts.ReleaseString = ""
	}
	opts.DisableRootfsVerification = (*rootfsVerification == no)
	opts.ClobberStateful = (*clobberStateful == yes)
	if *clearTpmOwner == auto {
		opts.ClearTpmOwner = opts.ClobberStateful
	} else {
		opts.ClearTpmOwner = (*clearTpmOwner == yes)
	}

	return target, opts, nil
}

func CLIMain(ctx context.Context, t0 time.Time, args []string) error {
	target, opts, err := cliParse(args)
	if err != nil {
		return err
	}

	if err := Main(ctx, t0, target, &opts); err != nil {
		return err
	}

	log.Println("DUT flashed successfully")

	return nil
}
