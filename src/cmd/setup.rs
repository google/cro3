// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::fs;

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Error;
use anyhow::Result;
use argh::FromArgs;
use lium::util::gen_path_in_lium_dir;
use lium::util::get_stdout;
use lium::util::run_bash_command;

#[derive(FromArgs, PartialEq, Debug)]
/// setup development environment
#[argh(subcommand, name = "setup")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}
#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    Env(ArgsEnv),
    BashCompletion(ArgsBashCompletion),
}
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::Env(args) => run_env(args),
        SubCommand::BashCompletion(args) => run_bash_completion(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// Check if this machine is ready to develop CrOS and do fix as needed
#[argh(subcommand, name = "env")]
pub struct ArgsEnv {}
fn run_env(_args: &ArgsEnv) -> Result<()> {
    eprintln!("Checking the environment...");
    let print_err_and_ignore = |e: Error| -> Result<()> {
        eprintln!("FAIL: {}", e);
        Ok(())
    };
    check_gsutil().or_else(print_err_and_ignore)?;
    Ok(())
}

fn check_gsutil() -> Result<()> {
    let result = run_bash_command("which gsutil", None)?;
    result
        .status
        .exit_ok()
        .context(anyhow!("Failed to run `which gsutil`"))?;
    let result = get_stdout(&result);
    eprintln!("{}", result);
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// Install bash completion for lium
#[argh(subcommand, name = "bash-completion")]
pub struct ArgsBashCompletion {}
fn run_bash_completion(_args: &ArgsBashCompletion) -> Result<()> {
    eprintln!("Installing bash completion...");
    fs::write(
        gen_path_in_lium_dir("lium.bash")?,
        include_bytes!("lium.bash"),
    )?;
    run_bash_command(
        "grep 'lium' ~/.bash_completion || echo \". ~/.lium/lium.bash\" >> ~/.bash_completion",
        None,
    )?
    .status
    .exit_ok()?;
    eprintln!(
        "Installed ~/.lium/lium.bash and an entry in ~/.bash_completion. Please run `source \
         ~/.bash_completion` for the current shell."
    );
    Ok(())
}
