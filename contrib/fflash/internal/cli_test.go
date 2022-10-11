// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"fmt"
	"regexp"
	"testing"

	"github.com/frankban/quicktest"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/dut"
)

func TestCLIParse(t *testing.T) {
	for name, test := range map[string]struct {
		args   []string
		target string
		opts   Options
	}{
		"defaults": {
			args:   []string{"dut"},
			target: "dut",
			opts:   Options{},
		},
		"clobber": {
			args:   []string{"dut", "--clobber-stateful=yes"},
			target: "dut",
			opts: Options{
				FlashOptions: dut.FlashOptions{
					ClobberStateful: true,
					ClearTpmOwner:   true, // follows --clobber-stateful by default
				},
			},
		},
		"clobber-but-not-clear-tpm": {
			args:   []string{"dut", "--clobber-stateful=yes", "--clear-tpm-owner=no"},
			target: "dut",
			opts: Options{
				FlashOptions: dut.FlashOptions{
					ClobberStateful: true,
					ClearTpmOwner:   false,
				},
			},
		},
	} {
		t.Run(name, func(t *testing.T) {
			qt := quicktest.New(t)
			target, opts, err := cliParse(test.args)
			qt.Assert(err, quicktest.IsNil)
			qt.Check(target, quicktest.Equals, test.target)
			qt.Check(opts, quicktest.Equals, test.opts)
		})
	}
}

func TestCLIParseErrors(t *testing.T) {
	for name, test := range map[string]struct {
		args      []string
		errString string
	}{
		"excess-args": {
			args:      []string{"a", "b"},
			errString: "error: unexpected b, try --help",
		},
		"missing-dut": {
			args:      nil,
			errString: `error: required argument 'dut-host' not provided, try --help`,
		},
		"invalid-flag": {
			args:      []string{"dut", "--invalid-flag"},
			errString: `error: unknown long flag '--invalid-flag', try --help`,
		},
	} {
		t.Run(name, func(t *testing.T) {
			qt := quicktest.New(t)
			_, _, err := cliParse(test.args)
			qt.Check(err, quicktest.ErrorMatches, regexp.QuoteMeta(test.errString))
		})
	}
}

func TestCLIParseExits(t *testing.T) {
	for name, test := range map[string]struct {
		args       []string
		exitStatus int
	}{
		"help": {
			args:       []string{"--help"},
			exitStatus: 0,
		},
	} {
		t.Run(name, func(t *testing.T) {
			qt := quicktest.New(t)

			qt.Assert(
				func() {
					cliParse(test.args)
				},
				quicktest.PanicMatches,
				fmt.Sprintf(`unexpected call to os.Exit\(%d\) during test`, test.exitStatus),
			)
		})
	}
}
