// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use argh::FromArgs;
use lium::chroot::Chroot;
use lium::repo::get_repo_dir;
use lium::servo::reset_devices;
use lium::servo::LocalServo;
use lium::servo::ServoList;
use lium::servo::ServodConnection;
use lium::util::gen_path_in_lium_dir;
use lium::util::lium_dir;
use lium::util::run_bash_command;
use std::fs::read_to_string;
use std::process;
use std::time::Duration;

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
    Get(ArgsGet),
    List(ArgsList),
    Kill(ArgsKill),
    Reset(ArgsReset),
    Shell(ArgsShell),
}
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::Control(args) => run_control(args),
        SubCommand::Get(args) => run_get(args),
        SubCommand::List(args) => run_list(args),
        SubCommand::Kill(args) => run_kill(args),
        SubCommand::Reset(args) => run_reset(args),
        SubCommand::Shell(args) => run_shell(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// get servo attributes
#[argh(subcommand, name = "get")]
pub struct ArgsGet {
    /// servo serial
    #[argh(option)]
    serial: String,

    /// name of attribute
    #[argh(positional)]
    key: String,
}
pub fn run_get(args: &ArgsGet) -> Result<()> {
    let list = ServoList::read()?;
    let s = list.find_by_serial(&args.serial)?;
    s.reset()?;
    std::thread::sleep(Duration::from_millis(1000));
    match args.key.as_str() {
        "ipv6_addr" => {
            println!("{}", s.read_ipv6_addr()?);
        }
        "ec_version" => {
            println!("{}", s.read_ec_version()?);
        }
        "model" => {
            println!(
                "{}",
                s.read_ec_version()?
                    .split('_')
                    .next()
                    .context("failed to parse")?
            );
        }
        "board" => {
            run_bash_command(
                "wget -N https://dl.google.com/edgedl/chromeos/recovery/recovery.conf",
                Some(&lium_dir()?),
            )?;
            let _list = read_to_string(gen_path_in_lium_dir("recovery.conf")?)?;
        }
        "gbb_flags" => {
            let repo = get_repo_dir(&None)?;
            println!("{:#X}", s.read_gbb_flags(&repo)?);
        }
        key => {
            return Err(anyhow!("attribute {key} is not defined"));
        }
    }
    Ok(())
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
    reset_devices(&args.serials)
}

#[derive(FromArgs, PartialEq, Debug)]
/// list servo-compatible devices (Servo V4, Servo V4p1, SuzyQable)
#[argh(subcommand, name = "list")]
pub struct ArgsList {
    /// update the cached servo info. It will take a few seconds per servo.
    #[argh(switch)]
    update: bool,
}
pub fn run_list(args: &ArgsList) -> Result<()> {
    if args.update {
        ServoList::update()?;
    }
    let list = ServoList::read()?;
    println!("{}", list);
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
    let list = ServoList::read()?;
    let s = list.find_by_serial(&args.serial)?;
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
