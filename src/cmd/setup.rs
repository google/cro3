// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use std::fs;

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Error;
use anyhow::Result;
use argh::FromArgs;
use lium::servo::LocalServo;
use lium::util::gen_path_in_lium_dir;
use lium::util::get_stdout;
use lium::util::run_bash_command;

#[derive(FromArgs, PartialEq, Debug)]
/// DUT controller
#[argh(subcommand, name = "setup")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}
#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    Dut(ArgsDut),
    Env(ArgsEnv),
    BashCompletion(ArgsBashCompletion),
}
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::Dut(args) => run_dut(args),
        SubCommand::Env(args) => run_env(args),
        SubCommand::BashCompletion(args) => run_bash_completion(args),
    }
}

fn is_ccd_opened(cr50: &LocalServo) -> Result<bool> {
    let ccd_state = cr50.run_cmd("Shell", "ccd")?;
    let ccd_state = ccd_state
        .split('\n')
        .rev()
        .find(|line| line.starts_with("State: "))
        .context("Could not detect CCD state")?
        .trim();
    eprintln!("{}: {:?}", cr50.serial(), ccd_state);
    if ccd_state == "State: Locked" {
        Ok(false)
    } else if ccd_state == "State: Opened" {
        Ok(true)
    } else {
        Err(anyhow!("Unexpected ccd state: {}", ccd_state))
    }
}

fn setup_dut(cr50: &LocalServo) -> Result<()> {
    if !is_ccd_opened(cr50)? {
        // Get rma_auth_challenge first, to get the code correctly
        let rma_auth_challenge = cr50.run_cmd("Shell", "rma_auth")?;
        // Try ccd open first since pre-MP devices may be able to open ccd without rma_auth
        cr50.run_cmd("Shell", "ccd open")?;
        if !is_ccd_opened(cr50)? {
            eprintln!("Trying to get rma_auth challenge...");
            for _ in 0..3 {
                // Generate rma_auth URL to unlock and abort
                let rma_auth_challenge: Vec<&str> = rma_auth_challenge
                    .split('\n')
                    .map(|s| s.trim())
                    .filter(|s| !s.is_empty())
                    .collect();
                eprintln!("{:?}", rma_auth_challenge);
                let rma_auth_challenge = rma_auth_challenge
                    .iter()
                    .skip_while(|s| *s != &"generated challenge:")
                    .nth(1)
                    .context("Could not get rma_auth challenge")?;
                if !rma_auth_challenge.starts_with("RMA Auth error") {
                    return Err(anyhow!("Visit https://chromeos.google.com/partner/console/cr50reset?challenge={rma_auth_challenge} to get the unlock code and run `lium servo shell --serial {} --cmd 'rma_auth ${{UNLOCK_CODE}}'` to get the ccd unlocked. (cr50_shell = {}, ap_shell = {}, ec_shell = {})", cr50.serial(), cr50.tty_path("Shell")?, cr50.tty_path("AP")?, cr50.tty_path("EC")?));
                }
                eprintln!("Failed: {rma_auth_challenge}");
                eprintln!("retrying in 3 sec...");
                std::thread::sleep(std::time::Duration::from_secs(3));
            }
        }
    }
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// Setup a DUT for dev
#[argh(subcommand, name = "dut")]
pub struct ArgsDut {}
fn run_dut(_args: &ArgsDut) -> Result<()> {
    let servo_list = LocalServo::discover()?;
    let cr50_list: Vec<LocalServo> = servo_list
        .iter()
        .filter(|e| e.product() == "Cr50" || e.product() == "Ti50")
        .cloned()
        .collect();

    println!("{} Cr50 found.", cr50_list.len());
    for cr50 in cr50_list {
        if let Err(e) = setup_dut(&cr50) {
            eprintln!("{:?}", e);
            continue;
        }
    }
    Ok(())
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
        "Installed ~/.lium/lium.bash and an entry in ~/.bash_completion. Please reload your shell."
    );
    Ok(())
}
