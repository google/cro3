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
use regex::Regex;
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

    /// flash a locally-built image instead of remote prebuilts
    #[argh(switch)]
    use_local_image: bool,
}
pub fn run(args: &Args) -> Result<()> {
    // repo path is needed since cros flash outside chroot only works within the cros checkout
    let repo = &get_repo_dir(&args.repo)?;

    // Determine a BOARD to flash
    let board = match (&args.board, &args.dut) {
        (Some(board), None) => board.clone(),
        (_, Some(dut)) => {
            ensure_testing_rsa_is_there()?;
            let dut = &DutInfo::new(dut)?;
            let board_from_dut = dut
                .info()
                .get("board")
                .context("Failed to get --board from ")?
                .clone();
            if let Some(board_from_arg) = &args.board {
                // The board name may have suffix '64' or '-*', so get the first alphabet
                // sequence as the base board name.
                let re = Regex::new(r"(^[[:alpha:]]*)")?;
                let cap_arg = if let Some(cap) = re.captures(board_from_arg) {
                    cap
                } else {
                    return Err(anyhow!(
                        "{} doesn not match the board name pattern.",
                        board_from_arg
                    ));
                };
                let cap_dut = re.captures(&board_from_dut).unwrap();
                if cap_arg[1] != cap_dut[1] {
                    return Err(anyhow!("Given BOARD does not match with DUT: {} is given but {} is installed on {:?}", board_from_arg, board_from_dut, dut));
                }
                board_from_arg.to_string()
            } else {
                board_from_dut
            }
        }
        (None, None) => return Err(anyhow!("Please specify --board or --dut")),
    };

    // Determine an image to flash
    let image_path = match (&args.version, args.use_local_image) {
        (Some(version), false) => {
            let version = if version == "latest-dev" {
                version.clone()
            } else {
                lookup_full_version(version)?
            };
            format!("xBuddy://remote/{board}/{version}/test")
        }
        (Some(_version), true) => {
            todo!("flashing local image other than latest is not yet supported")
        }
        (None, true) => {
            format!("xBuddy://local/{board}/latest/test")
        }
        (None, false) => {
            format!("xBuddy://remote/{board}/latest-dev/test")
        }
    };

    // Determine a destination
    let destination = match (&args.dut, args.usb) {
        (Some(dut), false) => {
            ensure_testing_rsa_is_there()?;
            let dut = &DutInfo::new(dut)?;
            dut.ssh().host_and_port()
        }
        (None, true) => "usb://".to_string(),
        _ => return Err(anyhow!("Please specify either --dut or --usb")),
    };
    let cmd = Command::new("cros")
        .current_dir(repo)
        .args([
            "flash",
            "--clobber-stateful",
            "--clear-tpm-owner",
            "-vvv",
            "--disable-rootfs-verification",
            &destination,
            &image_path,
        ])
        .spawn()?;
    let result = cmd.wait_with_output()?;
    if !result.status.success() {
        println!("cros sdk failed");
    }
    Ok(())
}
