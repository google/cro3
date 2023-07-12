// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Error;
use anyhow::Result;
use argh::FromArgs;
use lium::chroot::Chroot;
use lium::config::Config;
use lium::cros::ensure_testing_rsa_is_there;
use lium::dut::register_dut;
use lium::dut::DutInfo;
use lium::repo::get_repo_dir;
use lium::servo::get_cr50_attached_to_servo;
use lium::servo::get_servo_attached_to_cr50;
use lium::servo::LocalServo;
use lium::servo::ServoList;
use lium::util::gen_path_in_lium_dir;
use lium::util::get_stdout;
use lium::util::run_bash_command;
use std::fs;

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
    if ccd_state == "State: Locked" {
        Ok(false)
    } else if ccd_state == "State: Opened" {
        Ok(true)
    } else {
        Err(anyhow!("Unexpected ccd state: {}", ccd_state))
    }
}

/// Make DUTs connected via Servo ready for development
/// "Ready for development" means:
/// - CCD (Closed Case Debugging) is in "Open" state
/// - A Servo is attached correctly
/// - At least one Ethernet connection is available (so MAC addr and an IP address is known)
fn setup_dut_ccd_open(cr50: &LocalServo) -> Result<()> {
    if let Ok(servo) = get_servo_attached_to_cr50(cr50) {
        servo.reset()?;
    }
    cr50.reset()?;
    std::thread::sleep(std::time::Duration::from_secs(1));
    let list = ServoList::discover()?;
    // Lookup cr50 again, since its usb path can be changed after resetting Servo
    let cr50 = list.find_by_serial(cr50.serial())?;
    if is_ccd_opened(cr50)? {
        eprintln!("CCD is Opened");
        return Ok(());
    }
    // Get rma_auth_challenge first, to get the code correctly
    let rma_auth_challenge = cr50.run_cmd("Shell", "rma_auth")?;
    // Try ccd open first since pre-MP devices may be able to open ccd without rma_auth
    cr50.run_cmd("Shell", "ccd open")?;
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
            eprintln!("CCD unlock is required.");
            eprintln!(
                r#"If you are eligible, visit https://chromeos.google.com/partner/console/cr50reset?challenge={rma_auth_challenge} to get the unlock code and paste the output below. ( For Googlers, go/rma-auth has more details. )"#,
            );
            eprintln!("If not, follow https://chromium.googlesource.com/chromiumos/platform/ec/+/cr50_stab/docs/case_closed_debugging_cr50.md#ccd-open to do this manually.");
            let mut input = String::new();
            std::io::stdin()
                .read_line(&mut input)
                .context("Failed to read a line")?;
            let response = cr50
                .run_cmd(
                    "Shell",
                    &format!(
                        "rma_auth {}",
                        input
                            .trim()
                            .split(':')
                            .last()
                            .context("code is invalid")?
                            .trim()
                    ),
                )
                .context("Failed to run rma_auth command")?;
            return Err(anyhow!("response: {response}"));
        }
        eprintln!("Failed: {rma_auth_challenge}");
        eprintln!("retrying in 3 sec...");
        std::thread::sleep(std::time::Duration::from_secs(3));
    }
    Err(anyhow!("Failed to get rma_auth code."))
}

fn ensure_dut_network_connection(servo: &LocalServo) -> Result<DutInfo> {
    register_dut(&servo.read_ipv6_addr()?)
}

fn ensure_dev_gbb_flags(repo: &str, cr50: &LocalServo) -> Result<()> {
    let chroot = Chroot::new(repo)?;
    chroot.run_bash_script_in_chroot(
        "read gbb flags",
        &format!(
            "sudo flashrom -p raiden_debug_spi:target=AP,serial={} -r -i GBB:/tmp/gbb.bin",
            cr50.serial()
        ),
        None,
    )?;
    chroot.run_bash_script_in_chroot(
        "generate a new gbb",
        "sudo futility gbb -s --flags=0x40b9 /tmp/gbb.bin /tmp/gbb2.bin",
        None,
    )?;
    chroot.run_bash_script_in_chroot(
        "write gbb flags",
        &format!("sudo flashrom -p raiden_debug_spi:target=AP,serial={} -w -i GBB:/tmp/gbb2.bin --noverify-all", cr50.serial()),
        None
        )?;
    Ok(())
}

fn setup_dut(repo: &str, servo: &LocalServo) -> Result<()> {
    let cr50 = get_cr50_attached_to_servo(servo)?;
    ensure_testing_rsa_is_there()?;
    let config = Config::read()?;
    if config.default_ipv6_prefix().is_none() {
        return Err(anyhow!(
            "Please set `lium config set default_ipv6_prefix ${{PREFIX}}`"
        ));
    }

    eprintln!("Setting up DUT: {}", cr50.serial());
    setup_dut_ccd_open(&cr50)?;
    eprintln!("Using Servo: {}", servo.serial());
    if ensure_dut_network_connection(servo).is_err() {
        ensure_dev_gbb_flags(repo, &cr50)?;
    }
    let dut = ensure_dut_network_connection(servo)?;
    eprintln!("DUT is ready!");
    eprintln!("export DUT={}", dut.id());
    eprintln!("export SERVO_SERIAL={}", servo.serial());
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// Setup a DUT for dev using Servo
#[argh(subcommand, name = "dut")]
pub struct ArgsDut {
    /// servo serial
    #[argh(option)]
    serial: String,
    /// target cros repo dir. If omitted, current directory will be used.
    #[argh(option)]
    repo: Option<String>,
    /// do ccd unlock only
    #[argh(switch)]
    ccd_unlock: bool,
}
fn run_dut(args: &ArgsDut) -> Result<()> {
    let repo = get_repo_dir(&args.repo)?;
    let list = ServoList::discover()?;
    let servo = list.find_by_serial(&args.serial).context(
        "No Servos or Cr50 are detected. Please check the servo connection, try another side of USB port, attach servo directly with a host instead of via hub, etc...")?;
    eprintln!("Using {} {}", servo.product(), servo.serial());
    if args.ccd_unlock {
        let cr50 = get_cr50_attached_to_servo(servo)?;
        setup_dut_ccd_open(&cr50)
    } else {
        setup_dut(&repo, servo)
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
        "Installed ~/.lium/lium.bash and an entry in ~/.bash_completion. Please run `source ~/.bash_completion` for the current shell."
    );
    Ok(())
}
