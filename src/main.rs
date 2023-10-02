// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

#![feature(exit_status_error)]
#![feature(result_option_inspect)]

use anyhow::Result;

extern crate lazy_static;

mod cmd;

fn main() -> Result<()> {
    let args: cmd::TopLevel = argh::from_env();
    cmd::run(&args)
}
