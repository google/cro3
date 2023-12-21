// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use anyhow::Result;
use argh::FromArgs;
use lium::chroot::Chroot;
use lium::dut::SshInfo;
use lium::repo::get_cros_dir;

#[derive(FromArgs, PartialEq, Debug)]
/// run in chroot
#[argh(subcommand, name = "chroot")]
pub struct Args {
    /// target cros repo dir
    #[argh(option)]
    cros: Option<String>,
    /// DUT env var in chroot
    #[argh(option)]
    dut: Option<String>,
    /// BOARD env var in chroot
    #[argh(option)]
    board: Option<String>,
    /// if specified, run the command in chroot and exit.
    #[argh(option)]
    cmd: Option<String>,

    #[argh(option, hidden_help)]
    repo: Option<String>,
}
#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    let repo = get_cros_dir(&args.cros)?;
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
    if let Some(cmd) = &args.cmd {
        let mut script = String::new();
        for l in additional_args {
            script.push_str(&format!("{l}\n"));
        }
        script.push_str(cmd);
        chroot.run_bash_script_in_chroot("exec", &script, None)?;
    } else {
        chroot.open_chroot(additional_args.as_slice())?;
    }
    Ok(())
}
