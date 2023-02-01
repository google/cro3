// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use argh::FromArgs;
use lium::cache::KvCache;
use lium::chroot::Chroot;
use lium::cros::ensure_testing_rsa_is_there;
use lium::dut::SshInfo;
use lium::repo::get_repo_dir;

#[derive(FromArgs, PartialEq, Debug)]
/// Tast test wrapper
#[argh(subcommand, name = "tast")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}

pub static TEST_CACHE: KvCache<Vec<String>> = KvCache::new("tast_cache");
static PUBLIC_BUNDLE: &str = "public";

#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    List(ArgsList),
    Run(ArgsRun),
}
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::List(args) => run_tast_list(args),
        SubCommand::Run(args) => run_tast_run(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// Get tast test for the target DUT
#[argh(subcommand, name = "list")]
pub struct ArgsList {
    /// target cros repo directory
    #[argh(option)]
    repo: Option<String>,

    /// target DUT
    #[argh(option)]
    dut: Option<String>,

    /// glob pattern of the listint test
    #[argh(positional)]
    tests: Option<String>,
}
fn run_tast_list(args: &ArgsList) -> Result<()> {
    if args.tests.is_none() {
        // TODO: support glob matching
        if let Ok(Some(tests)) = TEST_CACHE.get(PUBLIC_BUNDLE) {
            for t in &tests {
                println!("{t}");
            }
            return Ok(());
        }
    }
    let dut = if let Some(_dut) = &args.dut {
        _dut
    } else {
        return Err(anyhow!("No cache found. Need --dut option to run"));
    };

    ensure_testing_rsa_is_there()?;
    let repodir = get_repo_dir(&args.repo)?;
    let chroot = Chroot::new(&repodir)?;
    let ssh = SshInfo::new(dut).context("failed to create SshInfo")?;
    // setup port forwarding for chroot.
    let (fwdcmd, port) = ssh.start_ssh_forwarding_range((4100, 4199))?;
    let filter = if let Some(_pat) = &args.tests {
        _pat
    } else {
        "*"
    };

    // TODO: automatically support internal tests
    let list = chroot.exec_in_chroot(&["tast", "list", &format!("127.0.0.1:{}", port), filter])?;

    let tests: Vec<String> = list.lines().map(|s| s.to_string()).collect::<Vec<_>>();
    TEST_CACHE.set(PUBLIC_BUNDLE, tests)?;

    println!("{list}");

    drop(fwdcmd);
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// Get tast test for the target DUT
#[argh(subcommand, name = "run")]
pub struct ArgsRun {
    /// target cros repo directory
    #[argh(option)]
    repo: Option<String>,

    /// target DUT
    #[argh(option)]
    dut: String,

    /// test name or pattern
    #[argh(positional)]
    tests: String,
}
fn run_tast_run(args: &ArgsRun) -> Result<()> {
    ensure_testing_rsa_is_there()?;
    let repodir = get_repo_dir(&args.repo)?;
    let chroot = Chroot::new(&repodir)?;
    let ssh = SshInfo::new(&args.dut).context("failed to create SshInfo")?;
    // setup port forwarding for chroot.
    let (fwdcmd, port) = ssh.start_ssh_forwarding_range((4100, 4199))?;
    let filter = &args.tests;

    // TODO: automatically support internal tests
    chroot.run_bash_script_in_chroot(
        "tast_run_cmd",
        &format!("tast run -installbuilddeps 127.0.0.1:{port} {filter}"),
        None,
    )?;

    drop(fwdcmd);
    Ok(())
}
