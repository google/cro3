// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use anyhow::anyhow;
use anyhow::Result;
use argh::FromArgs;
use lium::config::Config;

#[derive(FromArgs, PartialEq, Debug)]
/// create a virtual machine
#[argh(subcommand, name = "vm")]
pub struct Args {}

pub fn run(args: &Args) -> Result<()> {
    let _arg = args;

    let config = Config::read()?;
    if !config.is_internal() {
        return Err(anyhow!(
            "vm subcommand is currently only supported for google internal use"
        ));
    }

    Ok(())
}
