// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use anyhow::anyhow;
use anyhow::Result;
use argh::FromArgs;
use lium::chroot::Chroot;
use lium::cros::ensure_testing_rsa_is_there;
use lium::dut::SshInfo;
use lium::repo::get_repo_dir;
use regex_macro::regex;

#[derive(FromArgs, PartialEq, Debug)]
/// cros deploy wrapper
#[argh(subcommand, name = "deploy")]
pub struct Args {
    /// target cros repo dir
    #[argh(option)]
    repo: Option<String>,

    /// a DUT identifier (e.g. 127.0.0.1, localhost:2222)
    #[argh(option)]
    dut: String,

    /// package to deploy (space separated)
    #[argh(option)]
    packages: String,

    /// if specified, it will skip automatic reboot
    #[argh(switch)]
    skip_reboot: bool,
}
pub fn run(args: &Args) -> Result<()> {
    ensure_testing_rsa_is_there()?;
    let target = SshInfo::new(&args.dut)?;
    println!("Target DUT is {:?}", target);
    let board = target.get_board()?;
    let packages = &args.packages;
    let re_cros_kernel = regex!(r"chromeos-kernel-");
    let target = SshInfo::new(&args.dut)?;
    let target = if target.needs_port_forwarding_in_chroot() {
        let port = target.start_ssh_forwarding_range_background(4100..4200)?;
        SshInfo::new_host_and_port("localhost", port)?
    } else {
        target
    };
    let chroot = Chroot::new(&get_repo_dir(&args.repo)?)?;

    let mut iter = args
        .packages
        .split_whitespace()
        .filter(|s| re_cros_kernel.is_match(s));
    if iter.clone().count() > 1 {
        return Err(anyhow!(
            "There are more than 2 kernel packages. Please specify one of them."
        ));
    }
    let kernel_pkg = iter.next();

    let mut user_pkgs = String::new();
    args.packages.split_whitespace().for_each(|s| {
        if !re_cros_kernel.is_match(s) {
            user_pkgs.push_str(&format!("{s} "))
        }
    });
    if !user_pkgs.is_empty() {
        chroot.run_bash_script_in_chroot(
            "deploy",
            &format!(
                r"cros-workon-{board} start {packages} && cros deploy {} {user_pkgs}",
                target.host_and_port()
            ),
            None,
        )?;
    }

    if kernel_pkg.is_some() {
        if iter.next().is_some() {
            return Err(anyhow!(
                "There are more than 2 kernel packages. Please specify one of them."
            ));
        }
        chroot.run_bash_script_in_chroot(
            "update_kernel",
            &format!(
                r###"
cros-workon-{board} start {packages}
~/trunk/src/scripts/update_kernel.sh --remote={} --ssh_port {} --remote_bootargs
"###,
                target.host(),
                target.port()
            ),
            None,
        )?;
    } else if !args.skip_reboot {
        println!("Rebooting DUT...");
        target.run_cmd_piped(&["reboot; exit"])?;
    }
    Ok(())
}
