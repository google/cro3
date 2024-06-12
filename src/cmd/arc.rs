// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

//! ## ARC (Android Runtime on Chrome) related utilities
//! This feature is mainly for the internal developers.

use std::process::Command;

use anyhow::Result;
use argh::FromArgs;
use cro3::chroot::Chroot;
use cro3::cros::ensure_testing_rsa_is_there;
use cro3::dut::SshInfo;
use cro3::repo::get_cros_dir;
use tracing::error;
use tracing::info;

#[derive(FromArgs, PartialEq, Debug)]
/// control ARC
#[argh(subcommand, name = "arc")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}
#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    GuestKernelUprev(ArgsGuestKernelUprev),
    Flash(ArgsArcFlash),
    Logcat(ArgsLogcat),
}
#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::GuestKernelUprev(args) => run_guest_kernel_uprev(args),
        SubCommand::Flash(args) => run_arc_flash(args),
        SubCommand::Logcat(args) => run_logcat(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// ARCVM kernel sync to ACK
#[argh(subcommand, name = "guest_kernel_uprev")]
pub struct ArgsGuestKernelUprev {
    /// target cros repo dir
    #[argh(option)]
    cros: Option<String>,

    #[argh(option, hidden_help)]
    repo: Option<String>,
}
fn run_guest_kernel_uprev(args: &ArgsGuestKernelUprev) -> Result<()> {
    let chroot = Chroot::new(&get_cros_dir(&args.cros)?)?;
    chroot.run_bash_script_in_chroot(
        "arc_guest_kernel_uprev",
        r###"
cd ~/chromiumos/src/third_party/kernel/v5.10-arcvm
# merge the updates from the ACK
if ! git config remote.aosp.url > /dev/null; then
  # add aosp remote
  git remote add aosp https://android.googlesource.com/kernel/common
fi
if $(git rev-parse --is-shallow-repository); then
  # disables git gc
  git config --global gc.auto 0
  git fetch --unshallow cros chromeos-5.10-arcvm
  git fetch --unshallow aosp android12-5.10-lts
fi
git fetch cros chromeos-5.10-arcvm
git fetch aosp android12-5.10-lts

export ARCVM_KERNEL_5_10_UPDATE=chromeos-5.10-arcvm_`date +%F`
git checkout -b ${ARCVM_KERNEL_5_10_UPDATE} cros/chromeos-5.10-arcvm
git merge -m "update wip" --no-ff aosp/android12-5.10-lts
        "###,
        None,
    )?;
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// DUT ARC image flasher
#[argh(subcommand, name = "flash")]
pub struct ArgsArcFlash {
    /// cros repo dir
    #[argh(option)]
    cros: Option<String>,

    /// ARC version (optional)
    #[argh(option)]
    version: Option<String>,

    /// image type (default: userdebug)
    #[argh(option)]
    image_type: Option<String>,

    /// target DUT
    #[argh(option)]
    dut: String,

    /// force flash
    #[argh(switch)]
    force: bool,

    #[argh(option, hidden_help)]
    repo: Option<String>,
}
fn run_arc_flash(args: &ArgsArcFlash) -> Result<()> {
    let repo = &get_cros_dir(&args.cros)?;
    ensure_testing_rsa_is_there()?;
    let target = &SshInfo::new(&args.dut)?;
    let mut different = false;

    info!("Checking arch...");
    let arch = target.get_arch()?;

    info!("Checking version...");
    let cur_version = target.get_arc_version()?;
    let version = if let Some(_version) = &args.version {
        _version.clone()
    } else {
        cur_version.clone()
    };
    if version != cur_version {
        different = true;
    };

    info!("Checking ARC device...");
    let device = target.get_arc_device()?;

    info!("Checking current image type...");
    let cur_itype = target.get_arc_image_type()?;
    let itype = if let Some(_itype) = &args.image_type {
        _itype.clone()
    } else {
        String::from("userdebug")
    };
    if itype != cur_itype {
        different = true;
    }

    if !different {
        info!("Specified ARC image is already installed.");
        if !args.force {
            return Ok(());
        } else {
            info!("Forcibly flash again.");
        }
    }

    let cmd = Command::new(
        "src/private-overlays/project-cheets-private/scripts/deploy_prebuilt_android.py",
    )
    .current_dir(repo)
    .args([
        "--bid",
        &version,
        "--target",
        &format!("{device}_{arch}-{itype}"),
        &target.host_and_port(),
    ])
    .spawn()?;
    let result = cmd.wait_with_output()?;
    if !result.status.success() {
        error!("prebuilt ARC flash failed");
    }

    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// logcat wrapper
#[argh(subcommand, name = "logcat")]
pub struct ArgsLogcat {
    /// target DUT
    #[argh(option)]
    dut: String,
}
fn run_logcat(args: &ArgsLogcat) -> Result<()> {
    let remote = SshInfo::new(&args.dut)?;
    let devices = remote.run_cmd_stdio("adb devices")?;
    if !devices.contains("localhost:22") {
        remote.run_cmd_piped(&["adb", "connect", "localhost:22"])?;
    }
    remote.run_cmd_piped(&["adb", "logcat"])?;
    Ok(())
}
