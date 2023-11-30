// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use anyhow::bail;
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
/// run Tast test
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
#[tracing::instrument(level = "trace")]
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
    bail!("No cache found")
}

fn print_cached_tests(filter: &Pattern, bundles: &Vec<&str>) -> Result<()> {
    if bundles.is_empty() {
        print_cached_tests_in_bundle(filter, DEFAULT_BUNDLE)
    } else {
        // Ensure all bundles are cached.
        for b in bundles {
            if TEST_CACHE.get(b)?.is_none() {
                bail!("No cache found for {b}.");
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
    let port = ssh.start_ssh_forwarding_range_background(4100..4200)?;

    // To avoid "build failed: failed checking build deps:" error
    chroot.run_bash_script_in_chroot("update_board_chroot", "update_chroot", None)?;

    if bundles.is_empty() {
        update_cached_tests_in_bundle(DEFAULT_BUNDLE, &chroot, port)
    } else {
        for b in bundles {
            update_cached_tests_in_bundle(b, &chroot, port)?
        }
        Ok(())
    }
}

fn run_tast_list(args: &ArgsList) -> Result<()> {
    let filter = args
        .tests
        .as_ref()
        .map(|s| Pattern::new(s))
        .unwrap_or_else(|| Pattern::new("*"))?;
    let config = Config::read()?;
    let bundles = config.tast_bundles();

    if print_cached_tests(&filter, &bundles).is_ok() || args.cached {
        return Ok(());
    }

    let dut = args
        .dut
        .as_ref()
        .expect("Test name is not cached. Please rerun with --dut <DUT>");

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

    /// test options (e.g. "-var ...")
    #[argh(option)]
    option: Option<String>,

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

fn run_test_with_bundle(
    bundle: &str,
    filter: &Pattern,
    chroot: &Chroot,
    port: u16,
    opt: Option<&str>,
) -> Result<()> {
    chroot.run_bash_script_in_chroot(
        "tast_run_cmd",
        &format!(
            "tast run -installbuilddeps -buildbundle={bundle} {} 127.0.0.1:{port} {filter}",
            opt.unwrap_or("")
        ),
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
    let opt = args.option.as_deref();

    let config = Config::read()?;
    let bundles = config.tast_bundles();
    if bundles.is_empty() {
        run_test_with_bundle(DEFAULT_BUNDLE, &filter, &chroot, port, opt)?
    } else {
        for b in bundles {
            if bundle_has_test(b, &filter) {
                run_test_with_bundle(b, &filter, &chroot, port, opt)?
            }
        }
    }

    Ok(())
}
