// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use anyhow::Result;
use argh::FromArgs;
use lium::config::Config;

#[derive(FromArgs, PartialEq, Debug)]
/// configure lium
#[argh(subcommand, name = "config")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}
#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    Set(ArgsSet),
    Show(ArgsShow),
    Clear(ArgsClear),
}
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::Clear(args) => run_clear(args),
        SubCommand::Set(args) => run_set(args),
        SubCommand::Show(args) => run_show(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// Clear a config variable
#[argh(subcommand, name = "clear")]
pub struct ArgsClear {
    /// key of a config
    #[argh(positional)]
    key: String,
}
fn run_clear(args: &ArgsClear) -> Result<()> {
    let key = args.key.as_str();
    let mut config = Config::read()?;
    config.clear(key)
}

#[derive(FromArgs, PartialEq, Debug)]
/// Set a config variable
#[argh(subcommand, name = "set")]
pub struct ArgsSet {
    /// key of a config
    #[argh(positional)]
    key: String,
    /// value of a config
    #[argh(positional)]
    values: Vec<String>,
}
fn run_set(args: &ArgsSet) -> Result<()> {
    let key = args.key.as_str();
    let values = &args.values;
    let mut config = Config::read()?;
    config.set(key, values.as_slice())
}

#[derive(FromArgs, PartialEq, Debug)]
/// Show config variables
#[argh(subcommand, name = "show")]
pub struct ArgsShow {}
fn run_show(_args: &ArgsShow) -> Result<()> {
    let config = Config::read()?;
    println!("{}", serde_json::to_string_pretty(&config)?);
    Ok(())
}
