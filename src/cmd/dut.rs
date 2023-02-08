// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use argh::FromArgs;
use lazy_static::lazy_static;
use lium::cros;
use lium::dut::discover_local_duts;
use lium::dut::DutInfo;
use lium::dut::MonitoredDut;
use lium::dut::SshInfo;
use lium::dut::SSH_CACHE;
use lium::util::run_bash_command;
use rayon::prelude::*;
use std::collections::HashMap;
use std::env::current_exe;
use std::io::stdout;
use std::io::Write;
use std::thread;
use std::time;
use termion::screen::IntoAlternateScreen;

#[derive(FromArgs, PartialEq, Debug)]
/// DUT controller
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
    Proxy(ProxyArgs),
    Shell(ArgsDutShell),
    Monitor(ArgsDutMonitor),
    Pull(ArgsPull),
    Push(ArgsPush),
    Vnc(ArgsVnc),
}
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::ArcInfo(args) => run_arc_info(args),
        SubCommand::Discover(args) => run_discover(args),
        SubCommand::Do(args) => run_dut_do(args),
        SubCommand::Info(args) => run_dut_info(args),
        SubCommand::KernelConfig(args) => run_dut_kernel_config(args),
        SubCommand::List(args) => run_dut_list(args),
        SubCommand::Proxy(args) => run_proxy(args),
        SubCommand::Shell(args) => run_dut_shell(args),
        SubCommand::Monitor(args) => run_dut_monitor(args),
        SubCommand::Pull(args) => run_dut_pull(args),
        SubCommand::Push(args) => run_dut_push(args),
        SubCommand::Vnc(args) => run_dut_vnc(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// Pull files from DUT
#[argh(subcommand, name = "pull")]
struct ArgsPull {
    /// DUT which the files are pulled from
    #[argh(positional)]
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
    /// DUT which the files are pushed to
    #[argh(positional)]
    dut: String,

    /// pulled file names
    #[argh(positional)]
    files: Vec<String>,

    /// destination directory (required)
    #[argh(option)]
    dest: String,
}

fn run_dut_push(args: &ArgsPush) -> Result<()> {
    cros::ensure_testing_rsa_is_there()?;
    let target = &SshInfo::new(&args.dut)?;

    target.send_files(&args.files, Some(&args.dest))
}

#[derive(FromArgs, PartialEq, Debug)]
/// Open Vnc from DUT
#[argh(subcommand, name = "vnc")]
struct ArgsVnc {
    /// DUT which the files are pushed to
    #[argh(positional)]
    dut: String,

    /// local port (default: 5900)
    #[argh(option)]
    port: Option<u16>,
}

fn run_dut_vnc(args: &ArgsVnc) -> Result<()> {
    cros::ensure_testing_rsa_is_there()?;
    let target = &SshInfo::new(&args.dut)?;
    let port = if let Some(_port) = args.port {
        _port
    } else {
        5900
    };
    let mut child = target.start_port_forwarding(5900, port, "kmsvnc")?;
    let mut shown = false;

    loop {
        if let Some(status) = child.try_status()? {
            eprintln!("Failed to connect to {}: {}", &args.dut, status);
            return Ok(());
        } else if !shown {
            println!("Connected. Please run `xtightvncviewer -encodings raw localhost:5900`");
            shown = true;
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
    let mut reconnecting_all = false;
    let mut gcert_ok = true;
    loop {
        // Draw headers.
        write!(
            screen,
            "{}{}",
            termion::clear::All,
            termion::cursor::Goto(1, 1)
        )?;
        println!("{}", MonitoredDut::get_status_header());

        if gcert_ok {
            reconnecting_all = true;
            for target in targets.iter_mut() {
                println!("{}", target.get_status()?);
                if !target.reconnecting() {
                    reconnecting_all = false;
                }
            }
        }

        if reconnecting_all || !gcert_ok {
            // All connection is reconnecting state. Need to check gcert.
            let out = run_bash_command("gcertstatus -quiet", None)?;
            if out.status.exit_ok().is_err() {
                eprintln!("DUTs are disconnected because gcert is expired. Please update it.");
                gcert_ok = false;
            } else {
                gcert_ok = true;
            }
        }
        thread::sleep(time::Duration::from_secs(5))
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// open a SSH shell
#[argh(subcommand, name = "shell")]
struct ArgsDutShell {
    /// a DUT identifier (e.g. 127.0.0.1, localhost:2222)
    #[argh(positional)]
    dut: String,

    /// if specified, it will invoke autologin before opening a shell
    #[argh(switch)]
    autologin: bool,

    /// if specified, run the command on dut and exit. if not, it will open an interactive shell.
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
fn do_login(s: &SshInfo) -> Result<()> {
    s.run_autologin()
}
fn do_tail_messages(s: &SshInfo) -> Result<()> {
    s.run_cmd_piped(&["tail -f /var/log/messages"])
}
lazy_static! {
    static ref DUT_ACTIONS: HashMap<&'static str, DutAction> = {
        let mut m: HashMap<&'static str, DutAction> = HashMap::new();
        m.insert("reboot", Box::new(do_reboot));
        m.insert("login", Box::new(do_login));
        m.insert("tail_messages", Box::new(do_tail_messages));
        m
    };
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
        eprintln!("{:?}", DUT_ACTIONS.keys());
        return Ok(());
    }
    let unknown_actions: Vec<&String> = args
        .actions
        .iter()
        .filter(|s| !DUT_ACTIONS.contains_key(s.as_str()))
        .collect();
    if !unknown_actions.is_empty() || args.actions.is_empty() {
        return Err(anyhow!(
            "Unknown action: {unknown_actions:?}. See `lium dut do --list-actions` for available actions."
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
}
fn run_dut_list(args: &ArgsDutList) -> Result<()> {
    if args.clear {
        return SSH_CACHE.clear();
    }
    if args.ids {
        let keys: Vec<String> = SSH_CACHE.entries()?.keys().map(|s| s.to_string()).collect();
        println!("{}", keys.join(" "));
        return Ok(());
    }
    if args.status {
        eprintln!("Checking DUT status. Please be patient...");
        let status: Vec<(String, &str, SshInfo)> = SSH_CACHE
            .entries()?
            .par_iter()
            .map(|e| {
                let id = e.0;
                let info = DutInfo::new(id).map(|e| e.info().clone());
                let status = if let Ok(info) = info {
                    if Some(id) == info.get("dut_id") {
                        "Online"
                    } else {
                        "IP reused"
                    }
                } else {
                    "Offline"
                };
                (id.to_owned(), status, e.1.clone())
            })
            .collect();
        for s in status {
            println!("{:32} {:32} {:?}", s.0, s.1, s.2);
        }
        return Ok(());
    }
    for it in SSH_CACHE
        .entries()
        .context(anyhow!("SSH_CACHE is not initialized yet"))?
        .iter()
    {
        println!("{} {}", it.0, serde_json::to_string(it.1)?);
    }
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// show DUT info
#[argh(subcommand, name = "info")]
struct ArgsDutInfo {
    /// DUT identifiers (e.g. 127.0.0.1, localhost:2222, droid_NXHKDSJ003138124257611)
    #[argh(positional)]
    duts: Vec<String>,
    /// comma-separated list of attribute names. to show the full list, try `lium dut info --keys ?`
    #[argh(
        option,
        default = "String::from(\"timestamp,dut_id,hwid,address,release,model,serial,mac\")"
    )]
    keys: String,
}
fn run_dut_info(args: &ArgsDutInfo) -> Result<()> {
    let keys: Vec<&str> = args.keys.split(',').map(str::trim).collect();
    eprintln!("keys: ${keys:?}");
    let mut result = HashMap::new();
    for dut_id in &args.duts {
        let dut = DutInfo::new(dut_id)?;
        result.insert(dut_id, dut.info().clone());
        /*
        let disk_info = target.run_cmd_stdio(
        r#"lshw -json -c storage | jq '.[] | select(.id == "nvme") | {handle: .handle, vendor: .vendor, logicalname: .logicalname, product: .product, serial: .serial}'"#,
        )?;
        let ectool_temps_all = target.run_cmd_stdio(r#"ectool temps all"#)?;
        }
        */
    }
    let result = serde_json::to_string(&result)?;
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
    /// remote machine to do the scan. If not specified, run the discovery locally.
    #[argh(option)]
    remote: Option<String>,
}
pub fn run_discover(args: &ArgsDiscover) -> Result<()> {
    if let Some(remote) = &args.remote {
        eprintln!("Using remote machine: {}", remote);
        let lium_path = current_exe()?;
        eprintln!("lium executable path: {:?}", lium_path);
        let remote = SshInfo::new(remote)?;
        remote.send_files(
            &[lium_path.to_string_lossy().to_string()],
            Some(&"~/".to_string()),
        )?;
        remote.run_cmd_piped(&["~/lium", "dut", "discover"])?;
        Ok(())
    } else {
        let dut_list = discover_local_duts(args.interface.to_owned())?;
        let dut_list: Vec<HashMap<String, String>> =
            dut_list.iter().map(|e| e.info().to_owned()).collect();
        let dut_list = serde_json::to_string_pretty(&dut_list)?;
        println!("{}", dut_list);

        Ok(())
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// monitor local DUTs and establish a proxy
#[argh(subcommand, name = "proxy")]
pub struct ProxyArgs {
    /// a DUT identifier (e.g. 127.0.0.1, localhost:2222)
    #[argh(positional)]
    dut: String,
}
pub fn run_proxy(args: &ProxyArgs) -> Result<()> {
    // ssh -R 2501:10.10.10.85:22 hikalium.tok
    let target = &SshInfo::new(&args.dut)?;
    println!(
        r#"
Host hikalium*
    ControlMaster auto
    ControlPath ~/.ssh/mux-%r@%h:%p
    ControlPersist 10
    # Hosts
    RemoteForward 2300 {}
    # Vnc
    LocalForward 15900 127.0.0.1:5900
"#,
        target.host_and_port()
    );
    /*
    let mut screen = stdout().into_alternate_screen().unwrap();
    let mut dut_info = Vec::new();
    let mut needs_discovery = true;
    dut_info.resize(args.duts.len(), DutInfoCache::empty());
    loop {
        // Draw headers.
        let (screen_width, _) = terminal_size()?;
        write!(
            screen,
            "{}{}",
            termion::clear::All,
            termion::cursor::Goto(1, 1)
        )?;
        write!(
            screen,
            "lium dut proxy : DUTs under control: {}",
            dut_info.len()
        )?;
        write!(screen, "{}", termion::cursor::Goto(1, 2))?;
        for dut in &args.duts {
            writeln!(screen, "{dut:16}: ")?;
        }
        let progress_width = screen_width - 18;
        screen.flush().unwrap();
        for x in 0..progress_width {
            for (y, dut) in dut_info.iter_mut().enumerate() {
                if dut.target.is_none() {
                    dut.target = Some(SshInfo::new(&args.duts[y])?);
                }
                write!(
                    screen,
                    "{}{}",
                    cursor::Goto(1 + (screen_width - progress_width) + x, (y + 2).try_into()?),
                    "o",
                )?;
                screen.flush().unwrap();
                thread::sleep(Duration::from_millis(100));
            }
        }
    }
    */
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
