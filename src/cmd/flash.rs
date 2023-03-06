// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use crate::lookup_full_version;
use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use argh::FromArgs;
use lium::cros::ensure_testing_rsa_is_there;
use lium::dut::DutInfo;
use lium::repo::get_repo_dir;
use std::process::Command;

#[derive(FromArgs, PartialEq, Debug)]
/// Flash CrOS images
#[argh(subcommand, name = "flash")]
pub struct Args {
    /// flash to a USB stick
    #[argh(switch)]
    usb: bool,

    /// flash to a dut
    #[argh(option)]
    dut: Option<String>,

    /// target cros repo dir
    #[argh(option)]
    repo: Option<String>,

    /// target BOARD
    #[argh(option)]
    board: Option<String>,

    /// chromiumos version to flash
    #[argh(option)]
    version: Option<String>,
}
pub fn run(args: &Args) -> Result<()> {
    let repo = &get_repo_dir(&args.repo)?;
    let version = args
        .version
        .clone()
        .unwrap_or_else(|| "latest-dev".to_string());
    match (&args.dut, args.usb) {
        (Some(dut), false) => {
            ensure_testing_rsa_is_there()?;
            let dut = &DutInfo::new(dut)?;
            eprintln!("{:?}", dut.info());
            let board = args
                .board
                .as_ref()
                .or_else(|| dut.info().get("board"))
                .context("Failed to determine BOARD. Please manually specify --board.")?;
            let version = if version == "latest-dev" {
                version
            } else {
                lookup_full_version(&version)?
            };
            let cmd = Command::new("cros")
                .current_dir(repo)
                .args([
                    "flash",
                    "--clobber-stateful",
                    "-vvv",
                    "--disable-rootfs-verification",
                    &dut.ssh().host_and_port(),
                    &format!("xBuddy://remote/{board}/{version}/test"),
                ])
                .spawn()?;
            let result = cmd.wait_with_output()?;
            if !result.status.success() {
                println!("cros sdk failed");
            }
            Ok(())
        }
        (None, true) => {
            let board = args.board.as_ref().context("BOARD is needed for --usb")?;
            let version = if version == "latest-dev" {
                version
            } else {
                lookup_full_version(&version)?
            };
            let cmd = Command::new("cros")
                .current_dir(repo)
                .args([
                    "flash",
                    "--clobber-stateful",
                    "--clear-tpm-owner",
                    "-vvv",
                    "--disable-rootfs-verification",
                    "usb://",
                    &format!("xBuddy://remote/{board}/{version}/test"),
                ])
                .spawn()?;
            let result = cmd.wait_with_output()?;
            if !result.status.success() {
                println!("cros sdk failed");
            }
            Ok(())
        }
        _ => Err(anyhow!("Please provide either --dut ${{DUT}} or --usb")),
    }
}
