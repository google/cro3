// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use anyhow::Result;
use argh::FromArgs;
use lium::chroot::Chroot;
use lium::dut::SshInfo;
use lium::repo::get_repo_dir;

#[derive(FromArgs, PartialEq, Debug)]
/// cros_sdk wrapper
#[argh(subcommand, name = "chroot")]
pub struct Args {
    /// target cros repo dir
    #[argh(option)]
    repo: Option<String>,
    /// DUT env var in chroot
    #[argh(option)]
    dut: Option<String>,
    /// BOARD env var in chroot
    #[argh(option)]
    board: Option<String>,
}
pub fn run(args: &Args) -> Result<()> {
    let repo = get_repo_dir(&args.repo)?;
    let mut additional_args = Vec::new();
    let mut ssh_forwarding_control: Option<async_process::Child> = None;
    if let Some(dut) = &args.dut {
        let dut = SshInfo::new(dut)?;
        ssh_forwarding_control = Some(dut.start_ssh_forwarding(2222)?);
        additional_args.push("DUT=localhost:2222".to_string());
    }
    if let Some(board) = &args.board {
        additional_args.push(format!("BOARD={board}"));
    }
    let chroot = Chroot::new(&repo)?;
    chroot.open_chroot(additional_args.as_slice())?;
    drop(ssh_forwarding_control);
    Ok(())
}
