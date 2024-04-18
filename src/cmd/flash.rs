// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

//! ## Flash images (cros flash wrapper)
//! ```
//! # Flash an image into a remote DUT
//! cro3 flash --cros ${CROS} --dut ${DUT}
//! # Flash an image into a USB stick
//! cro3 flash --cros ${CROS} --usb --board ${BOARD}
//! ```

use std::process::Command;

use anyhow::anyhow;
use anyhow::bail;
use anyhow::Result;
use argh::FromArgs;
use cro3::cros::ensure_testing_rsa_is_there;
use cro3::cros::lookup_full_version;
use cro3::dut::DutInfo;
use cro3::repo::get_cros_dir;
use regex::Regex;
use tracing::error;
use tracing::info;

fn get_board_from_dut(dut: &str) -> Result<String> {
    let dut = DutInfo::new(dut)?;
    dut.info()
        .get("board")
        .cloned()
        .ok_or(anyhow!("Failed to get --board from "))
}

/// Determine a BOARD to flash, based on the parameters.
/// If arg_dut is specified, this function will check if the board given via
/// args is compatible with the BOARD of an image which is currently installed
/// on the DUT.
fn determine_board_to_flash(
    arg_dut: &Option<String>,
    arg_board: &Option<String>,
) -> Result<String> {
    match (arg_dut, arg_board) {
        (None, None) => bail!("Please specify --board or --dut"),
        (Some(dut), None) => get_board_from_dut(dut),
        (None, Some(board)) => Ok(board.to_string()),
        (Some(dut), Some(board_from_arg)) => {
            // Check if the base board names (without suffix '64' or '-*') are matched
            // to avoid flashing an unsupported image
            let board_from_dut = get_board_from_dut(dut)?;
            // Board has variants with suffixes (connected by dash), so need to compare
            // the first part.
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
                return Err(anyhow!(
                    "Given BOARD does not match with DUT: {} is given but {} is installed on the \
                     DUT",
                    board_from_arg,
                    board_from_dut
                ));
            }
            // This has to return the board name given by --board because DUT may
            // not run a variant image.
            Ok(board_from_arg.to_string())
        }
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// flash image
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
    cros: Option<String>,

    /// target BOARD
    #[argh(option)]
    board: Option<String>,

    /// path to image to flash
    #[argh(option)]
    image: Option<String>,

    /// chromiumos version to flash (default: latest-dev)
    #[argh(option, default = "String::from(\"latest-dev\")")]
    version: String,

    /// flash a locally-built image instead of remote prebuilts
    #[argh(switch)]
    use_local_image: bool,

    /// flash recovery image (default: flash test image)
    #[argh(switch)]
    recovery: bool,

    /// flash image with rootfs verification (disable by default)
    #[argh(switch)]
    enable_rootfs_verification: bool,

    #[argh(option, hidden_help)]
    repo: Option<String>,
}
#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    // repo path is needed since cros flash outside chroot only works within the
    // cros checkout
    let repo = &get_cros_dir(&args.cros)?;

    let image_path = if let Some(image) = &args.image {
        // If --image is specified, use the local file
        image.clone()
    } else {
        let board_to_flash = determine_board_to_flash(&args.dut, &args.board)?;
        info!("{board_to_flash}");

        // Determine an image to flash
        let host = if args.use_local_image {
            "local"
        } else {
            "remote"
        };
        // if version is not specified on the command line, it will be set to "latest"
        // by argh
        let version = if &args.version == "latest"
            || &args.version == "latest-dev"
            || &args.version == "latest-official"
        {
            args.version.clone()
        } else {
            lookup_full_version(&args.version, &board_to_flash)?
        };
        if host == "local" && version != "latest" {
            return Err(anyhow!(
                "flashing local image other than `--version latest` is not yet supported"
            ));
        }
        let variant = if args.recovery { "recovery" } else { "test" };
        format!("xBuddy://{host}/{board_to_flash}/{version}/{variant}")
    };

    // Determine a destination
    let destination = match (&args.dut, args.usb) {
        (Some(dut), false) => {
            ensure_testing_rsa_is_there()?;
            let dut = &DutInfo::new(dut)?;
            dut.ssh().into_forwarded()?.host_and_port().to_string()
        }
        (None, true) => "usb://".to_string(),
        _ => bail!("Please specify either --dut or --usb"),
    };

    let mut cmd_args: Vec<&str> =
        Vec::from(["flash", "--clobber-stateful", "--clear-tpm-owner", "-vvv"]);
    if !args.enable_rootfs_verification {
        cmd_args.push("--disable-rootfs-verification");
    }
    cmd_args.push(&destination);
    cmd_args.push(&image_path);

    let cmd = Command::new("cros")
        .current_dir(repo)
        .args(cmd_args)
        .spawn()?;
    let result = cmd.wait_with_output()?;
    if !result.status.success() {
        error!("cros sdk failed");
    }
    Ok(())
}
