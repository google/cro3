// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use argh::FromArgs;
use glob::Pattern;
use lium::cache::KvCache;
use lium::chroot::Chroot;
use lium::config::Config;
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
static DEFAULT_BUNDLE: &str = "cros";

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

    /// only show cached list
    #[argh(switch)]
    cached: bool,
}

fn print_cached_tests_in_bundle(filter: &Pattern, bundle: &str) -> Result<()> {
    if let Ok(Some(tests)) = TEST_CACHE.get(bundle) {
        for t in &tests {
            if filter.matches(t) {
                println!("{t}");
            }
        }
        return Ok(());
    }
    Err(anyhow!("No cache found"))
}

fn print_cached_tests(filter: &Pattern, bundles: &Vec<&str>) -> Result<()> {
    if bundles.is_empty() {
        print_cached_tests_in_bundle(filter, DEFAULT_BUNDLE)
    } else {
        // Ensure all bundles are cached.
        for b in bundles {
            if TEST_CACHE.get(b)?.is_none() {
                return Err(anyhow!("No cache found for {b}."));
            }
        }
        for b in bundles {
            print_cached_tests_in_bundle(filter, b)?
        }
        Ok(())
    }
}

fn update_cached_tests_in_bundle(bundle: &str, chroot: &Chroot, port: u16) -> Result<()> {
    let list = chroot.exec_in_chroot(&[
        "tast",
        "list",
        "-installbuilddeps",
        &format!("--buildbundle={}", bundle),
        &format!("127.0.0.1:{}", port),
    ])?;
    let tests: Vec<String> = list.lines().map(|s| s.to_string()).collect::<Vec<_>>();
    TEST_CACHE.set(bundle, tests)?;
    Ok(())
}

fn update_cached_tests(bundles: &Vec<&str>, dut: &str, repodir: &str) -> Result<()> {
    ensure_testing_rsa_is_there()?;
    let chroot = Chroot::new(repodir)?;
    let ssh = SshInfo::new(dut).context("failed to create SshInfo")?;
    let (fwdcmd, port) = ssh.start_ssh_forwarding_range(4100..4200)?;

    let ret = if bundles.is_empty() {
        update_cached_tests_in_bundle(DEFAULT_BUNDLE, &chroot, port)
    } else {
        for b in bundles {
            update_cached_tests_in_bundle(b, &chroot, port)?
        }
        Ok(())
    };
    drop(fwdcmd);
    ret
}

fn run_tast_list(args: &ArgsList) -> Result<()> {
    let filter = if let Some(_tests) = &args.tests {
        Pattern::new(_tests)?
    } else {
        Pattern::new("*")?
    };
    let config = Config::read()?;
    let bundles = config.tast_bundles();

    if print_cached_tests(&filter, &bundles).is_ok() || args.cached {
        return Ok(());
    }

    let dut = if let Some(_dut) = &args.dut {
        _dut
    } else {
        return Err(anyhow!(
            "Please re-run with --dut option to cache test names"
        ));
    };

    update_cached_tests(&bundles, dut, &get_repo_dir(&args.repo)?)?;

    print_cached_tests(&filter, &bundles)?;

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

fn bundle_has_test(bundle: &str, filter: &Pattern) -> bool {
    if let Ok(Some(tests)) = TEST_CACHE.get(bundle) {
        for t in tests {
            if filter.matches(&t) {
                return true;
            }
        }
    }
    false
}

fn run_test_with_bundle(bundle: &str, filter: &Pattern, chroot: &Chroot, port: u16) -> Result<()> {
    chroot.run_bash_script_in_chroot(
        "tast_run_cmd",
        &format!("tast run -installbuilddeps -buildbundle={bundle} 127.0.0.1:{port} {filter}"),
        None,
    )?;
    Ok(())
}

fn run_tast_run(args: &ArgsRun) -> Result<()> {
    ensure_testing_rsa_is_there()?;
    let filter = Pattern::new(&args.tests)?;
    let repodir = get_repo_dir(&args.repo)?;
    let chroot = Chroot::new(&repodir)?;
    let ssh = SshInfo::new(&args.dut).context("failed to create SshInfo")?;
    // setup port forwarding for chroot.
    let port = ssh.start_ssh_forwarding_range_background(4100..4200)?;

    let config = Config::read()?;
    let bundles = config.tast_bundles();
    if bundles.is_empty() {
        run_test_with_bundle(DEFAULT_BUNDLE, &filter, &chroot, port)?
    } else {
        for b in bundles {
            if bundle_has_test(b, &filter) {
                run_test_with_bundle(b, &filter, &chroot, port)?
            }
        }
    }

    Ok(())
}
