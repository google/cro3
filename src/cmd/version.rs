// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use anyhow::Result;
use argh::FromArgs;

const VERSION: &str = env!("CARGO_PKG_VERSION");

#[derive(FromArgs, PartialEq, Debug)]
/// display version info
#[argh(subcommand, name = "version")]
pub struct Args {}

#[tracing::instrument(level = "trace")]
pub fn run(_args: &Args) -> Result<()> {
    println!("lium v{VERSION}");
    Ok(())
}
