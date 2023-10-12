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
use lium::util::lium_paths::gen_path_in_lium_dir;
use lium::util::shell_helpers::get_stdout;
use lium::util::shell_helpers::run_bash_command;
use tracing::error;
use tracing::info;
use tracing::warn;

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
    ZshCompletion(ArgsZshCompletion),
}
#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::Env(args) => run_env(args),
        SubCommand::BashCompletion(args) => run_bash_completion(args),
        SubCommand::ZshCompletion(args) => run_zsh_completion(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// Check if this machine is ready to develop CrOS and do fix as needed
#[argh(subcommand, name = "env")]
pub struct ArgsEnv {}
fn run_env(_args: &ArgsEnv) -> Result<()> {
    info!("Checking the environment...");
    let print_err_and_ignore = |e: Error| -> Result<()> {
        error!("FAIL: {}", e);
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
    info!("{}", result);
    Ok(())
}

fn shell_shared_setup() -> Result<(), Error> {
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
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// Install bash completion for lium
#[argh(subcommand, name = "bash-completion")]
pub struct ArgsBashCompletion {}
fn run_bash_completion(_args: &ArgsBashCompletion) -> Result<()> {
    warn!("Installing bash completion...");

    shell_shared_setup()?;

    warn!(
        "Installed ~/.lium/lium.bash and an entry in ~/.bash_completion. Please run `source \
         ~/.bash_completion` for the current shell."
    );

    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// Print zsh completion instructions for lium
#[argh(subcommand, name = "zsh-completion")]
pub struct ArgsZshCompletion {}
fn run_zsh_completion(_args: &ArgsZshCompletion) -> Result<()> {
    warn!("Installing zsh completion via bash compat...");

    shell_shared_setup()?;

    warn!("add the following to your zshrc: ");
    warn!("autoload -U +X compinit && compinit");
    warn!("autoload -U +X bashcompinit && bashcompinit");
    warn!("source ~/.bash_completion");

    Ok(())
}
