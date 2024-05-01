// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

//! ## Deploy packages
//! ```
//! cro3 deploy --cros $CROS --dut $DUT --package $PACKAGE_NAME --autologin
//! ```

use std::cmp::Ordering;

use anyhow::bail;
use anyhow::Result;
use argh::FromArgs;
use cro3::chroot::Chroot;
use cro3::cros::ensure_testing_rsa_is_there;
use cro3::dut::SshInfo;
use cro3::repo::get_cros_dir;
use once_cell::sync::Lazy;
use regex::Regex;
use tracing::info;

static RE_CROS_KERNEL: Lazy<Regex> = Lazy::new(|| Regex::new("chromeos-kernel-").unwrap());

#[derive(FromArgs, PartialEq, Debug)]
/// deploy package(s)
#[argh(subcommand, name = "deploy")]
pub struct Args {
    /// target cros repo dir
    #[argh(option)]
    cros: Option<String>,

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

    #[argh(option, hidden_help)]
    repo: Option<String>,
}

#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    ensure_testing_rsa_is_there()?;

    let target = SshInfo::new(&args.dut)?.into_forwarded()?;
    info!("Target DUT is {:?}", target);

    let board = target.get_board()?;
    let packages_str = args.packages.join(" ");
    let chroot = Chroot::new(&get_cros_dir(&args.cros)?)?;

    let kernel_pkg = extract_kernel_pkg(&args.packages)?;

    cros_workon_user_packages(&chroot, &board, &args.packages, &packages_str, &target)?;

    if kernel_pkg.is_some() {
        chroot.run_bash_script_in_chroot(
            "update_kernel",
            &format!(
                r###"
cros-workon-{board} start {packages_str}
TOPDIR=~/trunk
[ -d $TOPDIR ] || TOPDIR=~/chromiumos
$TOPDIR/src/scripts/update_kernel.sh {} --remote={} --ssh_port {} --remote_bootargs
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
        info!("Rebooting DUT...");
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
                r"cros-workon-{board} start {packages_str} && cros deploy --force {} {user_pkgs}",
                target.host_and_port()
            ),
            None,
        )?;
    }

    Ok(())
}
