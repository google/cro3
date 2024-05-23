// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

//! ## Controlling a Servo (Hardware debugging tool)
//! Note: the official document is [here](https://chromium.googlesource.com/chromiumos/third_party/hdctools/+/HEAD/docs/servo.md)
//! ```
//! # Show list of Servo / Cr50 devices
//! cro3 servo list
//!
//! # Do the same thing in JSON format
//! cro3 servo list --json
//!
//! # Reset Servo USB ports (useful when cro3 servo list does not work)
//! sudo `which cro3` servo reset
//! ```

use std::fs::read_to_string;
use std::process;

use anyhow::bail;
use anyhow::Context;
use anyhow::Result;
use argh::FromArgs;
use cro3::chroot::Chroot;
use cro3::repo::get_cros_dir;
use cro3::servo::get_servo_attached_to_cr50;
use cro3::servo::reset_devices;
use cro3::servo::LocalServo;
use cro3::servo::ServoList;
use cro3::servo::ServodConnection;
use cro3::util::cro3_paths::cro3_dir;
use cro3::util::cro3_paths::gen_path_in_cro3_dir;
use cro3::util::shell_helpers::run_bash_command;
use tracing::info;

#[derive(FromArgs, PartialEq, Debug)]
/// control Servo
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
    Show(ArgsShow),
}
#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::Control(args) => run_control(args),
        SubCommand::Get(args) => run_get(args),
        SubCommand::List(args) => run_list(args),
        SubCommand::Kill(args) => run_kill(args),
        SubCommand::Reset(args) => run_reset(args),
        SubCommand::Shell(args) => run_shell(args),
        SubCommand::Show(args) => run_show(args),
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
    let list = ServoList::discover()?;
    let s = list.find_by_serial(&args.serial)?;
    let s = get_servo_attached_to_cr50(s)?;
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
                Some(&cro3_dir()?),
            )?;
            let _list = read_to_string(gen_path_in_cro3_dir("recovery.conf")?)?;
        }
        "gbb_flags" => {
            let repo = get_cros_dir(None)?;
            println!("{:#X}", s.read_gbb_flags(&repo)?);
        }
        key => {
            bail!("attribute {key} is not defined");
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
    /// retrieve additional info as well (takes more time)
    #[argh(switch)]
    slow: bool,

    /// display space-separated Servo serials on one line (stable)
    #[argh(switch)]
    serials: bool,

    /// print in JSON format (no effect on --serials)
    #[argh(switch)]
    json: bool,
}
pub fn run_list(args: &ArgsList) -> Result<()> {
    let list = if args.slow {
        ServoList::discover_slow()?
    } else {
        ServoList::discover()?
    };
    if args.serials {
        let keys: Vec<String> = list
            .devices()
            .iter()
            .map(|s| s.serial().to_string())
            .collect();
        println!("{}", keys.join(" "));
        return Ok(());
    }
    if args.json {
        println!("{}", list);
        return Ok(());
    }
    println!("product         serial                          usb_sysfs_path");
    let devices = list.devices().clone();
    for s in devices {
        println!(
            "{:16}{:24}\t{}",
            s.product(),
            s.serial(),
            s.usb_sysfs_path()
        );
    }
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// monitor local DUTs and establish a proxy
#[argh(subcommand, name = "control")]
pub struct ArgsControl {
    /// path to chromiumos source checkout
    #[argh(option)]
    cros: String,
    /// a servo serial number. To list available servos, run `cro3 servo list`
    #[argh(option)]
    serial: String,
    /// arguments to pass to dut_control command
    #[argh(positional)]
    args: Vec<String>,

    #[argh(option, hidden_help)]
    repo: Option<String>,
}
pub fn run_control(args: &ArgsControl) -> Result<()> {
    let chroot = Chroot::new(&args.cros)?;
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
    info!("Killing old servod instances...");
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
    let list = ServoList::discover()?;
    let s = list.find_by_serial(&args.serial)?;
    if args.print_tty_path {
        info!("{}", s.tty_path(&args.tty_type)?);
        Ok(())
    } else if let Some(cmd) = &args.cmd {
        let ccd_state = s.run_cmd(&args.tty_type, cmd)?;
        info!("{}", ccd_state);
        Ok(())
    } else {
        bail!("invalid args. please check --help.")
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// show info related to a Servo
#[argh(subcommand, name = "show")]
pub struct ArgsShow {
    /// a Servo serial number
    #[argh(option)]
    servo: String,
    /// print info in JSON format
    #[argh(switch)]
    json: bool,
}
fn run_show(args: &ArgsShow) -> Result<()> {
    let list = ServoList::discover()?;
    let s = list.find_by_serial(&args.servo)?;
    if args.json {
        println!("{s}");
    } else {
        println!(
            "{} {} {}",
            s.serial(),
            s.usb_sysfs_path(),
            s.tty_path("Servo EC Shell")?
        );
    }
    Ok(())
}
