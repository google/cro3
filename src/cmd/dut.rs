// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::collections::HashMap;
use std::env::current_exe;
use std::fs::read_to_string;
use std::io::stdout;
use std::io::Read;
use std::io::Write;
use std::thread;
use std::time;

use anyhow::anyhow;
use anyhow::bail;
use anyhow::Context;
use anyhow::Result;
use argh::FromArgs;
use lazy_static::lazy_static;
use lium::chroot::Chroot;
use lium::cros;
use lium::dut::discover_local_nodes;
use lium::dut::fetch_dut_info_in_parallel;
use lium::dut::DutInfo;
use lium::dut::MonitoredDut;
use lium::dut::SshInfo;
use lium::dut::SSH_CACHE;
use lium::repo::get_repo_dir;
use lium::servo::get_cr50_attached_to_servo;
use lium::servo::LocalServo;
use lium::servo::ServoList;
use rayon::prelude::*;
use termion::screen::IntoAlternateScreen;
use tracing::error;
use tracing::info;
use tracing::warn;

#[derive(FromArgs, PartialEq, Debug)]
/// control DUT
#[argh(subcommand, name = "dut")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}
#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    ArcInfo(ArgsArcInfo),
    Discover(ArgsDiscover),
    Do(ArgsDutDo),
    Info(ArgsDutInfo),
    KernelConfig(ArgsDutKernelConfig),
    List(ArgsDutList),
    Shell(ArgsDutShell),
    Monitor(ArgsDutMonitor),
    Pull(ArgsPull),
    Push(ArgsPush),
    Setup(ArgsSetup),
    Vnc(ArgsVnc),
}
#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::ArcInfo(args) => run_arc_info(args),
        SubCommand::Discover(args) => run_discover(args),
        SubCommand::Do(args) => run_dut_do(args),
        SubCommand::Info(args) => run_dut_info(args),
        SubCommand::KernelConfig(args) => run_dut_kernel_config(args),
        SubCommand::List(args) => run_dut_list(args),
        SubCommand::Shell(args) => run_dut_shell(args),
        SubCommand::Monitor(args) => run_dut_monitor(args),
        SubCommand::Pull(args) => run_dut_pull(args),
        SubCommand::Push(args) => run_dut_push(args),
        SubCommand::Setup(args) => run_setup(args),
        SubCommand::Vnc(args) => run_dut_vnc(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// Pull files from DUT
#[argh(subcommand, name = "pull")]
struct ArgsPull {
    /// DUT which the files are pulled from
    #[argh(option)]
    dut: String,

    /// pulled file names
    #[argh(positional)]
    files: Vec<String>,

    /// destination directory (current directory by default)
    #[argh(option)]
    dest: Option<String>,
}

fn run_dut_pull(args: &ArgsPull) -> Result<()> {
    cros::ensure_testing_rsa_is_there()?;
    let target = &SshInfo::new(&args.dut)?;

    target.get_files(&args.files, args.dest.as_ref())
}

#[derive(FromArgs, PartialEq, Debug)]
/// Push files from DUT
#[argh(subcommand, name = "push")]
struct ArgsPush {
    /// destination DUT
    #[argh(option)]
    dut: String,

    /// destination directory on a DUT
    #[argh(option)]
    dest: Option<String>,

    /// source files
    #[argh(positional)]
    files: Vec<String>,
}

fn run_dut_push(args: &ArgsPush) -> Result<()> {
    cros::ensure_testing_rsa_is_there()?;
    let target = &SshInfo::new(&args.dut)?;

    target.send_files(&args.files, args.dest.as_ref())
}

#[derive(FromArgs, PartialEq, Debug)]
/// Open Vnc from DUT
#[argh(subcommand, name = "vnc")]
struct ArgsVnc {
    /// DUT which the files are pushed to
    #[argh(option)]
    dut: String,

    /// host port to forward (default: 5900)
    #[argh(option)]
    vnc_port: Option<u16>,
}

fn run_dut_vnc(args: &ArgsVnc) -> Result<()> {
    cros::ensure_testing_rsa_is_there()?;
    let target = &SshInfo::new(&args.dut)?;
    let vnc_port = args.vnc_port.unwrap_or(5900);
    let web_port = args.vnc_port.unwrap_or(6080);

    if let Err(e) = target.run_cmd_piped(&["kill -9 $(pgrep --full vnc)"]) {
        error!("Failed to kill previous vnc instance: {e}")
    }

    let mut child_kmsvnc = target.start_port_forwarding(vnc_port, 5900, "kmsvnc")?;
    let mut child_novnc = target.start_port_forwarding(web_port, 6080, "novnc")?;

    warn!("To use VNC via web browser, please open:");
    warn!("  http://localhost:{web_port}/vnc.html");
    warn!("To connect via VNC client directly, use:");
    warn!("  xtightvncviewer -encodings raw localhost:{vnc_port}");

    loop {
        if let Some(status) = child_kmsvnc.try_status()? {
            panic!("kmsvnc terminated {}: {}", &args.dut, status);
        }
        if let Some(status) = child_novnc.try_status()? {
            panic!("novnc terminated {}: {}", &args.dut, status);
        }
        thread::sleep(time::Duration::from_secs(5));
    }
}
#[derive(FromArgs, PartialEq, Debug)]
/// open a SSH monitor
#[argh(subcommand, name = "monitor")]
struct ArgsDutMonitor {
    /// DUT identifiers to monitor
    #[argh(positional)]
    duts: Vec<String>,
}

fn run_dut_monitor(args: &ArgsDutMonitor) -> Result<()> {
    cros::ensure_testing_rsa_is_there()?;
    let mut targets: Vec<MonitoredDut> = Vec::new();
    let mut port = 4022;

    for dut in &args.duts {
        targets.push(MonitoredDut::new(dut, port)?);
        port += 1;
    }

    let mut screen = stdout().into_alternate_screen().unwrap();
    loop {
        // Draw headers.
        write!(
            screen,
            "{}{}",
            termion::clear::All,
            termion::cursor::Goto(1, 1)
        )?;
        println!("{}", MonitoredDut::get_status_header());

        for target in targets.iter_mut() {
            println!("{}", target.get_status()?);
        }

        thread::sleep(time::Duration::from_secs(5))
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// open a SSH shell
#[argh(subcommand, name = "shell")]
struct ArgsDutShell {
    /// a DUT identifier (e.g. 127.0.0.1, localhost:2222)
    #[argh(option)]
    dut: String,

    /// if specified, it will invoke autologin before opening a shell
    #[argh(switch)]
    autologin: bool,

    /// if specified, run the command on dut and exit. if not, it will open an
    /// interactive shell.
    #[argh(positional)]
    args: Vec<String>,
}
fn run_dut_shell(args: &ArgsDutShell) -> Result<()> {
    cros::ensure_testing_rsa_is_there()?;
    let target = &SshInfo::new(&args.dut)?;
    if args.autologin {
        target.run_autologin()?;
    }
    if args.args.is_empty() {
        target.open_ssh()
    } else {
        target.run_cmd_piped(&args.args)
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// get the kernel configuration from the DUT
#[argh(subcommand, name = "kernel_config")]
struct ArgsDutKernelConfig {
    /// a DUT identifier (e.g. 127.0.0.1, localhost:2222)
    #[argh(positional)]
    dut: String,
}
fn run_dut_kernel_config(args: &ArgsDutKernelConfig) -> Result<()> {
    cros::ensure_testing_rsa_is_there()?;
    let target = &SshInfo::new(&args.dut)?;
    let config = target.get_host_kernel_config()?;
    println!("{}", config);
    Ok(())
}

type DutAction = Box<fn(&SshInfo) -> Result<()>>;
fn do_reboot(s: &SshInfo) -> Result<()> {
    s.run_cmd_piped(&["reboot; exit"])
}

enum PartitionSet {
    Primary,
    Secondary,
}
fn switch_partition_set(s: &SshInfo, target: PartitionSet) -> Result<()> {
    let rootdev = s.get_rootdev()?;
    let rootdisk = s.get_rootdisk()?;
    let part = s.get_partnum_info()?;
    let kern_a = part.get("kern_a").ok_or(anyhow!("KERN-A not found"))?;
    let kern_b = part.get("kern_b").ok_or(anyhow!("KERN-B not found"))?;
    let root_a = part.get("root_a").ok_or(anyhow!("ROOT-A not found"))?;
    let root_b = part.get("root_b").ok_or(anyhow!("ROOT-B not found"))?;
    let (current_name, current_kern, current_root, other_name, other_kern, other_root) =
        if rootdev.ends_with(root_a) {
            ("A", kern_a, root_a, "B", kern_b, root_b)
        } else if rootdev.ends_with(root_b) {
            ("B", kern_b, root_b, "A", kern_a, root_a)
        } else {
            bail!("unsupported partition layout");
        };
    let cmd = match target {
        PartitionSet::Primary => {
            println!("switching to primary: {current_name} ({rootdisk}p{current_root})");
            format!("cgpt prioritize -P2 -i {current_kern} {rootdisk}")
        }
        PartitionSet::Secondary => {
            println!("switching to secondary: {other_name} ({rootdisk}p{other_root})");
            format!("cgpt prioritize -P2 -i {other_kern} {rootdisk}")
        }
    };
    s.run_cmd_piped(&[cmd])
}
fn do_switch_to_primary(s: &SshInfo) -> Result<()> {
    switch_partition_set(s, PartitionSet::Primary)
}
fn do_switch_to_secondary(s: &SshInfo) -> Result<()> {
    switch_partition_set(s, PartitionSet::Secondary)
}
fn do_wait_online(s: &SshInfo) -> Result<()> {
    for _ in 0..100 {
        if s.run_cmd_piped(&["echo ok"]).is_ok() {
            return Ok(());
        }
    }
    bail!("do_wait_online timed out")
}
fn do_login(s: &SshInfo) -> Result<()> {
    s.run_autologin()
}
fn do_tail_messages(s: &SshInfo) -> Result<()> {
    s.run_cmd_piped(&["tail -f /var/log/messages"])
}
lazy_static! {
    static ref DUT_ACTIONS: HashMap<&'static str, DutAction> = {
        let mut m: HashMap<&'static str, DutAction> = HashMap::new();
        m.insert("wait_online", Box::new(do_wait_online));
        m.insert("reboot", Box::new(do_reboot));
        m.insert("switch_to_primary", Box::new(do_switch_to_primary));
        m.insert("switch_to_secondary", Box::new(do_switch_to_secondary));
        m.insert("login", Box::new(do_login));
        m.insert("tail_messages", Box::new(do_tail_messages));
        m
    };
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
        bail!("Unexpected ccd state: {}", ccd_state)
    }
}

fn do_rma_auth(cr50: &LocalServo) -> Result<()> {
    // Get rma_auth_challenge first, to get the code correctly
    let rma_auth_challenge = cr50.run_cmd("Shell", "rma_auth")?;
    // Try ccd open first since pre-MP devices may be able to open ccd without
    // rma_auth
    cr50.run_cmd("Shell", "ccd open")?;
    for _ in 0..3 {
        // Generate rma_auth URL to unlock and abort
        let rma_auth_challenge: Vec<&str> = rma_auth_challenge
            .split('\n')
            .map(|s| s.trim())
            .filter(|s| !s.is_empty())
            .collect();
        info!("{:?}", rma_auth_challenge);
        let rma_auth_challenge = rma_auth_challenge
            .iter()
            .skip_while(|s| *s != &"generated challenge:")
            .nth(1)
            .context("Could not get rma_auth challenge")?;
        if !rma_auth_challenge.starts_with("RMA Auth error") {
            error!("CCD unlock is required.");
            error!(
                r#"If you are eligible, visit https://chromeos.google.com/partner/console/cr50reset?challenge={rma_auth_challenge} to get the unlock code and paste the output below. ( For Googlers, go/rma-auth has more details. )"#,
            );
            error!("If not, follow https://chromium.googlesource.com/chromiumos/platform/ec/+/cr50_stab/docs/case_closed_debugging_cr50.md#ccd-open to do this manually.");
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
            bail!("response: {response}");
        }
        error!("Failed: {rma_auth_challenge}");
        error!("retrying in 3 sec...");
        std::thread::sleep(std::time::Duration::from_secs(3));
    }
    bail!("Failed to get rma_auth code.")
}

fn open_ccd(cr50: &LocalServo) -> Result<()> {
    let list = ServoList::discover()?;
    // Lookup cr50 again, since its usb path can be changed after resetting Servo
    let cr50 = list.find_by_serial(cr50.serial())?;
    let mut ccd = false;
    ccd |= is_ccd_opened(cr50)?;
    ccd |= is_ccd_opened(cr50)?;
    if ccd {
        info!("CCD is Opened already ({})", cr50.tty_path("Shell")?);
        return Ok(());
    }
    do_rma_auth(cr50)?;
    if !is_ccd_opened(cr50)? {
        return Err(anyhow!(
            "Could not open CCD after rma_auth ({})",
            cr50.tty_path("Shell")?
        ));
    }
    info!("CCD is Opened successfully ({})", cr50.tty_path("Shell")?);
    Ok(())
}

fn get_ccd_status(cr50: &LocalServo) -> Result<()> {
    let list = ServoList::discover()?;
    // Lookup cr50 again, since its usb path can be changed after resetting Servo
    let cr50 = list.find_by_serial(cr50.serial())?;
    if !is_ccd_opened(cr50)? {
        bail!("CCD is Closed ({})", cr50.tty_path("Shell")?);
    }
    info!("CCD is Opened ({})", cr50.tty_path("Shell")?);
    Ok(())
}

fn set_dev_gbb_flags(repo: &str, cr50: &LocalServo) -> Result<()> {
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
        &format!(
            "sudo flashrom -p raiden_debug_spi:target=AP,serial={} -w -i GBB:/tmp/gbb2.bin \
             --noverify-all",
            cr50.serial()
        ),
        None,
    )?;
    Ok(())
}

fn reset_gbb_flags(repo: &str, cr50: &LocalServo) -> Result<()> {
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
        "sudo futility gbb -s --flags=0x0 /tmp/gbb.bin /tmp/gbb2.bin",
        None,
    )?;
    chroot.run_bash_script_in_chroot(
        "write gbb flags",
        &format!(
            "sudo flashrom -p raiden_debug_spi:target=AP,serial={} -w -i GBB:/tmp/gbb2.bin \
             --noverify-all",
            cr50.serial()
        ),
        None,
    )?;
    Ok(())
}
fn is_ccd_testlab_enabled(cr50: &LocalServo) -> Result<bool> {
    let result = cr50
        .run_cmd("Shell", "ccd testlab")
        .context(anyhow!("Failed to run `ccd testlab` command"))?;
    Ok(result.contains("CCD test lab mode enabled"))
}
fn enable_ccd_testlab(servo: &LocalServo) -> Result<()> {
    let cr50 = get_cr50_attached_to_servo(servo)?;
    info!("Enabling CCD testlab mode of DUT: {}", cr50.serial());
    open_ccd(&cr50)?;
    if is_ccd_testlab_enabled(&cr50)? {
        info!("CCD testlab mode is already enabled");
        return Ok(());
    }
    let result = cr50
        .run_cmd("Shell", "ccd testlab")
        .context(anyhow!("Failed to run `ccd testlab` command"))?;
    if !result.trim().contains("CCD test lab mode enabled") {
        return Err(anyhow!(
            "CCD testlab mode is disabled. Please run `minicom -w -D {}` and run `ccd testlab \
             enable` on it and follow the instructions.",
            cr50.tty_path("Shell")?
        ));
    }
    Ok(())
}
fn check_ssh(servo: &LocalServo) -> Result<DutInfo> {
    let addr = servo.read_ipv6_addr()?;
    info!("IP address: {addr}");
    let dut = DutInfo::new(&addr)?;
    info!("PASS: {} @ {} is reachable via SSH", dut.id(), addr);
    Ok(dut)
}

/// Check if GBB flags are set for development.
fn check_dev_gbb_flags(dut: &DutInfo) -> Result<()> {
    let info = DutInfo::fetch_keys(dut.ssh(), &vec!["gbb_flags"])?;
    let gbb_flags = info
        .get("gbb_flags")
        .context("gbb_flags is not set")?
        .replace(r"0x", "");
    let gbb_flags = u64::from_str_radix(&gbb_flags, 16).context("failed to parse gbb_flags")?;
    info!("GBB flags: {gbb_flags:#10X}");
    if !gbb_flags & 0x19 != 0 {
        return Err(anyhow!(
            "GBB flags are not set properly for development. Please run:
                lium dut shell --dut [{0}] -- /usr/share/vboot/bin/set_gbb_flags.sh 0x19
                lium dut shell --dut [{0}] -- /usr/share/vboot/bin/set_gbb_flags.sh 0x19",
            info.get("ipv6_addr").context("Failed to get ipv6_addr")?
        ));
    }
    info!("PASS: GBB flags are set for dev");
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// Make DUTs connected via Servo ready for development
/// "Ready for development" means:
/// - CCD (Closed Case Debugging) is in "Open" state
/// - A Servo is attached correctly
/// - At least one Ethernet connection is available (so MAC addr and an IP
///   address is known)
/// - GBB flags are set to 0x19
/// - CCD testlab mode is enabled
#[argh(subcommand, name = "setup")]
struct ArgsSetup {
    /// servo serial
    #[argh(option)]
    serial: Option<String>,
    /// cros repo dir to use
    #[argh(option)]
    repo: Option<String>,
    /// do ccd open only
    #[argh(switch)]
    open_ccd: bool,
    /// check ccd status via servo
    #[argh(switch)]
    get_ccd_status: bool,
    /// check if GBB flags are set for development
    #[argh(switch)]
    check_dev_gbb_flags: bool,
    /// do gbb flags update only
    #[argh(switch)]
    set_dev_gbb_flags: bool,
    /// reset gbb flags only
    #[argh(switch)]
    reset_gbb_flags: bool,
    /// do ccd unlock only
    #[argh(switch)]
    enable_ccd_testlab: bool,
    /// check if the DUT is reachable via SSH
    #[argh(switch)]
    check_ssh: bool,
}
fn run_setup(args: &ArgsSetup) -> Result<()> {
    let repo = get_repo_dir(&args.repo)?;
    let servo = if let Some(serial) = &args.serial {
        let list = ServoList::discover()?;
        list.find_by_serial(serial)
            .context(format!(
                "
        Servo {serial} not found.
        Please check the servo connection, try another side of USB port, attach servo directly \
                 with a host instead of via hub, etc...
        `lium servo list` may be helpful.
        "
            ))?
            .clone()
    } else {
        let list = ServoList::discover()?;
        let list: Vec<LocalServo> = list
            .devices()
            .iter()
            .filter(|s| s.is_servo())
            .cloned()
            .collect();
        if list.len() != 1 {
            return Err(anyhow!(
                "Please specify --serial when multiple Servo is connected. `lium servo list` may \
                 be helpful."
            ));
        }
        list.first()
            .context(
                "Servo is not connected. Run `lium servo list` to check if Servo is connected.",
            )?
            .clone()
    };
    info!("Using {} {} as Servo", servo.product(), servo.serial());
    let cr50 = get_cr50_attached_to_servo(&servo)?;
    info!("Using {} {} as Cr50", cr50.product(), cr50.serial());
    if args.open_ccd {
        open_ccd(&cr50)?;
    } else if args.get_ccd_status {
        get_ccd_status(&cr50)?;
    } else if args.check_dev_gbb_flags {
        let dut = check_ssh(&servo)?;
        check_dev_gbb_flags(&dut)?;
    } else if args.set_dev_gbb_flags {
        set_dev_gbb_flags(&repo, &cr50)?;
    } else if args.reset_gbb_flags {
        reset_gbb_flags(&repo, &cr50)?;
    } else if args.enable_ccd_testlab {
        enable_ccd_testlab(&cr50)?;
    } else if args.check_ssh {
        check_ssh(&servo)?;
    } else {
        open_ccd(&cr50)?;
        enable_ccd_testlab(&cr50)?;
        let dut = check_ssh(&servo)?;
        check_dev_gbb_flags(&dut)?;
    }
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// send actions
#[argh(subcommand, name = "do")]
struct ArgsDutDo {
    /// a DUT identifier (e.g. 127.0.0.1, localhost:2222)
    #[argh(option)]
    dut: Option<String>,
    /// actions to do (--list-actions to see available options)
    #[argh(positional)]
    actions: Vec<String>,
    /// list available actions
    #[argh(switch)]
    list_actions: bool,
}
fn run_dut_do(args: &ArgsDutDo) -> Result<()> {
    cros::ensure_testing_rsa_is_there()?;
    if args.list_actions {
        println!(
            "{}",
            DUT_ACTIONS
                .keys()
                .map(|s| s.to_owned())
                .collect::<Vec<&str>>()
                .join(" ")
        );
        return Ok(());
    }
    let unknown_actions: Vec<&String> = args
        .actions
        .iter()
        .filter(|s| !DUT_ACTIONS.contains_key(s.as_str()))
        .collect();
    if !unknown_actions.is_empty() || args.actions.is_empty() {
        return Err(anyhow!(
            "Unknown action: {unknown_actions:?}. See `lium dut do --list-actions` for available \
             actions."
        ));
    }
    let dut = &SshInfo::new(args.dut.as_ref().context(anyhow!("Please specify --dut"))?)?;
    let actions: Vec<&DutAction> = args
        .actions
        .iter()
        .flat_map(|s| DUT_ACTIONS.get(s.as_str()))
        .collect();
    let actions: Vec<(&String, &&DutAction)> = args.actions.iter().zip(actions.iter()).collect();
    for (name, f) in actions {
        f(dut).context(anyhow!("DUT action: {name}"))?;
    }
    Ok(())
}

#[derive(Debug, Copy, Clone, PartialEq, Eq)]
enum DutStatus {
    Online,
    Offline,
    AddressReused,
}
#[derive(FromArgs, PartialEq, Debug)]
/// list all cached DUTs
#[argh(subcommand, name = "list")]
struct ArgsDutList {
    /// clear all DUT caches
    #[argh(switch)]
    clear: bool,

    /// display space-separated DUT IDs on one line (stable)
    #[argh(switch)]
    ids: bool,

    /// display current status of DUTs (may take a few moments)
    #[argh(switch)]
    status: bool,

    /// add a DUT to the list with the connection provided
    #[argh(option)]
    add: Option<String>,

    /// remove a DUT with a specified ID from the list
    #[argh(option)]
    remove: Option<String>,

    /// update the DUT list and show their status
    #[argh(switch)]
    update: bool,
}
fn run_dut_list(args: &ArgsDutList) -> Result<()> {
    if args.clear {
        return SSH_CACHE.clear();
    }
    let duts = SSH_CACHE
        .entries()
        .context(anyhow!("SSH_CACHE is not initialized yet"))?;
    if args.ids {
        let keys: Vec<String> = duts.keys().map(|s| s.to_string()).collect();
        println!("{}", keys.join(" "));
        return Ok(());
    }
    if let Some(dut_to_add) = &args.add {
        info!("Checking DutInfo of {dut_to_add}...");
        let info = DutInfo::new(dut_to_add)?;
        let id = info.id();
        let ssh = info.ssh();
        SSH_CACHE.set(id, ssh.clone())?;
        println!("Added: {:32} {}", id, serde_json::to_string(ssh)?);
        return Ok(());
    }
    if let Some(dut_to_remove) = &args.remove {
        SSH_CACHE.remove(dut_to_remove)?;
        info!("Removed: {dut_to_remove}",);
        return Ok(());
    }
    if args.status || args.update {
        warn!(
            "Checking status of {} DUTs. It will take a minute...",
            duts.len()
        );
        let duts: Vec<(String, DutStatus, SshInfo)> = duts
            .par_iter()
            .map(|e| {
                let id = e.0;
                let info = DutInfo::new(id).map(|e| e.info().clone());
                let status = if let Ok(info) = info {
                    if Some(id) == info.get("dut_id") {
                        DutStatus::Online
                    } else {
                        DutStatus::AddressReused
                    }
                } else {
                    DutStatus::Offline
                };
                (id.to_owned(), status, e.1.clone())
            })
            .collect();
        let (duts_to_be_removed, duts) = if args.update {
            (
                duts.iter()
                    .filter(|e| e.1 == DutStatus::AddressReused)
                    .cloned()
                    .collect(),
                duts.iter()
                    .filter(|e| e.1 != DutStatus::AddressReused)
                    .cloned()
                    .collect(),
            )
        } else {
            (Vec::new(), duts)
        };
        for dut in duts {
            println!("{:32} {:13} {:?}", dut.0, &format!("{:?}", dut.1), dut.2);
        }
        if !duts_to_be_removed.is_empty() {
            println!("\nFollowing DUTs are removed: ");
            for dut in duts_to_be_removed {
                println!("{:32} {:13} {:?}", dut.0, &format!("{:?}", dut.1), dut.2);
                SSH_CACHE.remove(&dut.0)?;
            }
        }
        return Ok(());
    }
    // List cached DUTs
    for it in duts.iter() {
        println!("{:32} {}", it.0, serde_json::to_string(it.1)?);
    }
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// show DUT info
#[argh(subcommand, name = "info")]
struct ArgsDutInfo {
    /// DUT identifiers (e.g. 127.0.0.1, localhost:2222,
    /// droid_NXHKDSJ003138124257611)
    #[argh(option)]
    dut: String,
    /// comma-separated list of attribute names. to show the full list, try
    /// `lium dut info --keys ?`
    #[argh(positional)]
    keys: Vec<String>,
}
fn run_dut_info(args: &ArgsDutInfo) -> Result<()> {
    let dut = &args.dut;
    let keys = if args.keys.is_empty() {
        vec!["timestamp", "dut_id", "release", "model", "serial", "mac"]
    } else {
        args.keys.iter().map(|s| s.as_str()).collect()
    };
    let ssh = SshInfo::new(dut)?;
    let info = DutInfo::fetch_keys(&ssh, &keys)?;
    let result = serde_json::to_string(&info)?;
    println!("{}", result);
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// discover DUTs on the same network
#[argh(subcommand, name = "discover")]
pub struct ArgsDiscover {
    /// A network interface to be used for the scan.
    /// if not specified, the first interface in the routing table will be used.
    #[argh(option)]
    interface: Option<String>,
    /// remote machine to do the scan. If not specified, run the discovery
    /// locally.
    #[argh(option)]
    remote: Option<String>,
    /// path to a list of DUT_IDs to scan.
    #[argh(option)]
    target_list: Option<String>,
    /// additional attributes to retrieve
    #[argh(positional, greedy)]
    extra_attr: Vec<String>,
}
pub fn run_discover(args: &ArgsDiscover) -> Result<()> {
    if let Some(remote) = &args.remote {
        info!("Using remote machine: {}", remote);
        let lium_path = current_exe()?;
        info!("lium executable path: {:?}", lium_path);
        let remote = SshInfo::new(remote)?;
        remote.send_files(
            &[lium_path.to_string_lossy().to_string()],
            Some(&"~/".to_string()),
        )?;
        let mut cmd = "~/lium dut discover".to_string();
        for ea in &args.extra_attr {
            cmd += " ";
            cmd += ea;
        }
        remote.run_cmd_piped(&[cmd])?;
        return Ok(());
    }
    let addrs = if let Some(target_list) = &args.target_list {
        let addrs: String = if target_list == "-" {
            let mut buffer = Vec::new();
            std::io::stdin().read_to_end(&mut buffer)?;
            Ok(std::str::from_utf8(&buffer)?.to_string())
        } else {
            read_to_string(target_list)
        }?;
        Ok(addrs
            .trim()
            .split('\n')
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(str::to_string)
            .collect())
    } else {
        discover_local_nodes(args.interface.to_owned())
    }?;
    info!("Found {} candidates. Checking...", addrs.len());
    let duts = fetch_dut_info_in_parallel(&addrs, &args.extra_attr)?;
    info!("Discovery completed with {} DUTs", duts.len());
    let duts: Vec<HashMap<String, String>> = duts.iter().map(|e| e.info().to_owned()).collect();
    let dut_list = serde_json::to_string_pretty(&duts)?;
    println!("{}", dut_list);

    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// get ARC information
#[argh(subcommand, name = "arc_info")]
struct ArgsArcInfo {
    /// a DUT identifier (e.g. 127.0.0.1, localhost:2222)
    #[argh(positional)]
    dut: String,
}
fn run_arc_info(args: &ArgsArcInfo) -> Result<()> {
    cros::ensure_testing_rsa_is_there()?;
    let target = &SshInfo::new(&args.dut)?;
    println!("arch: {}", target.get_arch()?);
    println!("ARC version: {}", target.get_arc_version()?);
    println!("ARC device: {}", target.get_arc_device()?);
    println!("image type: {}", target.get_arc_image_type()?);
    Ok(())
}
