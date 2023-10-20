// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::cmp::Ordering;

use anyhow::bail;
use anyhow::Result;
use argh::FromArgs;
use lium::chroot::Chroot;
use lium::cros::ensure_testing_rsa_is_there;
use lium::dut::SshInfo;
use lium::repo::get_repo_dir;
use once_cell::sync::Lazy;
use regex::Regex;

static RE_CROS_KERNEL: Lazy<Regex> = Lazy::new(|| Regex::new("chromeos-kernel-").unwrap());

#[derive(FromArgs, PartialEq, Debug)]
/// deploy package(s)
#[argh(subcommand, name = "deploy")]
pub struct Args {
    /// target cros repo dir
    #[argh(option)]
    repo: Option<String>,

    /// a DUT identifier (e.g. 127.0.0.1, localhost:2222)
    #[argh(option)]
    dut: String,

    /// packages to deploy
    #[argh(positional)]
    packages: Vec<String>,

    /// if specified, it will skip automatic reboot
    #[argh(switch)]
    skip_reboot: bool,

    /// use ab_update for kernel package
    #[argh(switch)]
    ab_update: bool,
}

#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    ensure_testing_rsa_is_there()?;

    let target = {
        let t = SshInfo::new(&args.dut)?;
        if t.needs_port_forwarding_in_chroot() {
            let port = t.start_ssh_forwarding_range_background(4100..4200)?;
            SshInfo::new_host_and_port("localhost", port)?
        } else {
            t
        }
    };
    println!("Target DUT is {:?}", target);

    let board = target.get_board()?;
    let packages_str = args.packages.join(" ");
    let chroot = Chroot::new(&get_repo_dir(&args.repo)?)?;

    let kernel_pkg = extract_kernel_pkg(&args.packages)?;

    cros_workon_user_packages(&chroot, &board, &args.packages, &packages_str, &target)?;

    if kernel_pkg.is_some() {
        chroot.run_bash_script_in_chroot(
            "update_kernel",
            &format!(
                r###"
cros-workon-{board} start {packages_str}
~/trunk/src/scripts/update_kernel.sh {} --remote={} --ssh_port {} --remote_bootargs
"###,
                if args.ab_update { "--ab_update" } else { "" },
                target.host(),
                target.port()
            ),
            None,
        )?;

        return Ok(());
    }

    if !args.skip_reboot {
        println!("Rebooting DUT...");
        target.run_cmd_piped(&["reboot; exit"])?;
    }

    Ok(())
}

fn extract_kernel_pkg(packages: &[String]) -> Result<Option<String>> {
    let kernel_packages: Vec<_> = packages
        .iter()
        .filter(|&s| RE_CROS_KERNEL.is_match(s))
        .collect();

    match kernel_packages.len().cmp(&1) {
        Ordering::Greater => {
            bail!("There are more than 2 kernel packages. Please specify one of them.");
        }
        Ordering::Equal => Ok(Some(kernel_packages[0].to_string())),
        _ => Ok(None),
    }
}

fn cros_workon_user_packages(
    chroot: &Chroot,
    board: &str,
    packages: &[String],
    packages_str: &str,
    target: &SshInfo,
) -> Result<()> {
    // Filter out all kernel packages and join them into a space seperated list.
    let user_pkgs: String = packages
        .iter()
        .filter(|&s| !RE_CROS_KERNEL.is_match(s))
        .map(|s| s.to_string())
        .collect::<Vec<_>>()
        .join(" ");

    if !user_pkgs.is_empty() {
        chroot.run_bash_script_in_chroot(
            "deploy",
            &format!(
                r"cros-workon-{board} start {packages_str} && cros deploy {} {user_pkgs}",
                target.host_and_port()
            ),
            None,
        )?;
    }

    Ok(())
}
