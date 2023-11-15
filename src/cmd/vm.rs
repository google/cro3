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
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}

#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    Connect(ArgsConnect),
    Setup(ArgsSetup),
    Start(ArgsStart),
    Push(ArgsPush),
}

#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    let config = Config::read()?;
    if !config.is_internal() {
        return Err(anyhow!(
            "vm subcommand is currently only supported for google internal use"
        ));
    }

    match &args.nested {
        SubCommand::Connect(args) => run_connect(args),
        SubCommand::Setup(args) => run_setup(args),
        SubCommand::Start(args) => run_start(args),
        SubCommand::Push(args) => run_push(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// connects to a running betty instance via SSH
#[argh(subcommand, name = "connect")]
pub struct ArgsConnect {
    /// extra arguments
    #[argh(option)]
    extra_args: Vec<String>,
}

fn run_connect(_args: &ArgsConnect) -> Result<()> {
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// run first time setup, installs necessary dependencies
#[argh(subcommand, name = "setup")]
pub struct ArgsSetup {
    /// extra arguments
    #[argh(option)]
    extra_args: Vec<String>,
}

fn run_setup(_args: &ArgsSetup) -> Result<()> {
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// start a betty VM instance
#[argh(subcommand, name = "start")]
pub struct ArgsStart {
    /// extra arguments
    #[argh(option)]
    extra_args: Vec<String>,
}

fn run_start(_args: &ArgsStart) -> Result<()> {
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// pushes an Android build a running betty instance
#[argh(subcommand, name = "push")]
pub struct ArgsPush {
    /// extra arguments
    #[argh(option)]
    extra_args: Vec<String>,
}

fn run_push(_args: &ArgsPush) -> Result<()> {
    Ok(())
}
