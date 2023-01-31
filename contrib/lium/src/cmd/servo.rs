// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use argh::FromArgs;
use lium::chroot::Chroot;
use lium::servo::LocalServo;
use lium::servo::ServodConnection;
use std::collections::HashSet;
use std::iter::FromIterator;
use std::process;

#[derive(FromArgs, PartialEq, Debug)]
/// DUT controller
#[argh(subcommand, name = "servo")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}
#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    Control(ArgsControl),
    List(ArgsList),
    Kill(ArgsKill),
    Reset(ArgsReset),
    Shell(ArgsShell),
}
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::Control(args) => run_control(args),
        SubCommand::List(args) => run_list(args),
        SubCommand::Kill(args) => run_kill(args),
        SubCommand::Reset(args) => run_reset(args),
        SubCommand::Shell(args) => run_shell(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// reset servo devices
#[argh(subcommand, name = "reset")]
pub struct ArgsReset {
    /// servo serials to reset (reset all devices if not specified)
    #[argh(positional)]
    serials: Vec<String>,
}
pub fn run_reset(args: &ArgsReset) -> Result<()> {
    let servo_info = LocalServo::discover()?;
    let mut servo_info: Vec<LocalServo> = if !args.serials.is_empty() {
        let serials: HashSet<_> = HashSet::from_iter(args.serials.iter());
        servo_info
            .iter()
            .filter(|s| serials.contains(&s.serial().to_string()))
            .cloned()
            .collect()
    } else {
        servo_info
    };
    for s in &mut servo_info {
        s.reset()?;
    }
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// list servo-compatible devices (Servo V4, Servo V4p1, SuzyQable)
#[argh(subcommand, name = "list")]
pub struct ArgsList {
    /// deep info retrieval. it will take a few seconds per servo.
    #[argh(switch)]
    deep: bool,
}
pub fn run_list(args: &ArgsList) -> Result<()> {
    let servo_info = if args.deep {
        // Slow path
        LocalServo::discover_slow()?
    } else {
        // Fast path
        LocalServo::discover()?
    };
    println!("{}", serde_json::to_string_pretty(&servo_info)?);
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// monitor local DUTs and establish a proxy
#[argh(subcommand, name = "control")]
pub struct ArgsControl {
    /// path to chromiumos source checkout
    #[argh(option)]
    repo: String,
    /// a servo serial number. To list available servos, run `lium servo list`
    #[argh(option)]
    serial: String,
    /// arguments to pass to dut_control command
    #[argh(positional)]
    args: Vec<String>,
}
pub fn run_control(args: &ArgsControl) -> Result<()> {
    let chroot = Chroot::new(&args.repo)?;
    let servod = ServodConnection::from_serial(&args.serial)
        .or_else(|_| LocalServo::from_serial(&args.serial)?.start_servod(&chroot))?;
    let output = servod.run_dut_control(&chroot, &args.args)?;
    println!("{}", output);
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// Kill all servods
#[argh(subcommand, name = "kill")]
pub struct ArgsKill {}
pub fn run_kill(_args: &ArgsKill) -> Result<()> {
    eprintln!("Killing old servod instances...");
    process::Command::new("sudo")
        .args(["pkill", "-f", "servod"])
        .spawn()?
        .wait_with_output()
        .context("Failed to kill servod")?;
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// run shell command
#[argh(subcommand, name = "shell")]
pub struct ArgsShell {
    /// print the tty path (e.g. /dev/ttyUSB0) for the shell
    #[argh(switch)]
    print_tty_path: bool,
    /// DUT serial number (e.g. 09803057-8C65B668) to use
    #[argh(option)]
    serial: String,
    /// tty type (e.g. EC, I2C, AP EC upgrade, AP, Shell, Firmware upgrade, ...)
    #[argh(option, default = "String::from(\"Shell\")")]
    tty_type: String,
    /// command to execute
    #[argh(option)]
    cmd: Option<String>,
}
fn run_shell(args: &ArgsShell) -> Result<()> {
    let servo_list = LocalServo::discover()?;
    let s = servo_list
        .iter()
        .find(|s| s.serial() == args.serial)
        .context("Servo not found with a given serial")?;
    if args.print_tty_path {
        eprintln!("{}", s.tty_path(&args.tty_type)?);
        Ok(())
    } else if let Some(cmd) = &args.cmd {
        let ccd_state = s.run_cmd(&args.tty_type, cmd)?;
        eprintln!("{}", ccd_state);
        Ok(())
    } else {
        Err(anyhow!("invalid args. please check --help."))
    }
}
