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
    if let Some(dut) = &args.dut {
        let dut = SshInfo::new(dut)?;
        let port = dut.start_ssh_forwarding_range_background(4100..4200)?;
        additional_args.push(format!("DUT=localhost:{port}"));
    }
    if let Some(board) = &args.board {
        additional_args.push(format!("BOARD={board}"));
    }
    let chroot = Chroot::new(&repo)?;
    chroot.open_chroot(additional_args.as_slice())?;
    Ok(())
}
