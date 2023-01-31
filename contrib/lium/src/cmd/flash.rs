// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use crate::lookup_full_version;
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
    #[argh(subcommand)]
    nested: SubCommand,
}
#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    Dut(ArgsDut),
    Usb(ArgsUsb),
}
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::Dut(args) => run_dut(args),
        SubCommand::Usb(args) => run_usb(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// flash CrOS image to DUT via ssh
#[argh(subcommand, name = "dut")]
pub struct ArgsDut {
    /// target DUT
    #[argh(positional)]
    dut: String,

    /// target cros repo dir
    #[argh(option)]
    repo: Option<String>,

    /// target board
    #[argh(option)]
    board: Option<String>,

    /// target board
    #[argh(option)]
    version: Option<String>,
}
pub fn run_dut(args: &ArgsDut) -> Result<()> {
    ensure_testing_rsa_is_there()?;
    let repo = &get_repo_dir(&args.repo)?;
    let version = args
        .version
        .clone()
        .unwrap_or_else(|| "latest-dev".to_string());
    let dut = &DutInfo::new(&args.dut)?;
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

#[derive(FromArgs, PartialEq, Debug)]
/// flash CrOS image to USB Stick
#[argh(subcommand, name = "usb")]
pub struct ArgsUsb {
    /// target board
    #[argh(option)]
    board: String,

    /// target cros repo dir
    #[argh(option)]
    repo: Option<String>,

    /// target board
    #[argh(option)]
    version: Option<String>,
}
pub fn run_usb(args: &ArgsUsb) -> Result<()> {
    ensure_testing_rsa_is_there()?;
    let repo = &get_repo_dir(&args.repo)?;
    let board = &args.board;
    let version = args
        .version
        .clone()
        .unwrap_or_else(|| "latest-dev".to_string());
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
