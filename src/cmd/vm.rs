// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use anyhow::anyhow;
use anyhow::Result;
use argh::FromArgs;
use lium::config::Config;

#[derive(FromArgs, PartialEq, Debug)]
/// create a virtual machine
#[argh(subcommand, name = "vm")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}

#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    Connect(ArgsConnect),
    Setup(ArgsSetup),
    Start(ArgsStart),
    Push(ArgsPush),
}

#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    let config = Config::read()?;
    if !config.is_internal() {
        return Err(anyhow!(
            "vm subcommand is currently only supported for google internal use"
        ));
    }

    match &args.nested {
        SubCommand::Connect(args) => run_connect(args),
        SubCommand::Setup(args) => run_setup(args),
        SubCommand::Start(args) => run_start(args),
        SubCommand::Push(args) => run_push(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// connects to a running betty instance via SSH
#[argh(subcommand, name = "connect")]
pub struct ArgsConnect {
    /// extra arguments
    #[argh(option)]
    extra_args: Vec<String>,
}

fn run_connect(_args: &ArgsConnect) -> Result<()> {
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// run first time setup, installs necessary dependencies
#[argh(subcommand, name = "setup")]
pub struct ArgsSetup {
    /// extra arguments
    #[argh(option)]
    extra_args: Vec<String>,
}

fn run_setup(_args: &ArgsSetup) -> Result<()> {
    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// start a betty VM instance
#[argh(subcommand, name = "start")]
pub struct ArgsStart {
    /// the BOARD to run (e.g. betty-pi-arc)
    #[argh(option, short = 'b')]
    board: String,

    /// reuse the VM image. It is true by default.
    #[argh(option, default = "true")]
    reuse_disk_image: bool,

    /// specifies the display device for the VM. "vnc" (default) creates a VNC
    /// display on localhost:5900; "virgl" enables guest 3D acceleration,
    /// assuming X11 (or use xvfb-run) and qemu compiled with GTK/virgl support;
    /// "none" removes the VGA device, which can be used to simulate the GCE
    /// environment (i.e. L1 betty).
    #[argh(option)]
    display: Option<String>,

    /// the ChromeOS version to use (e.g. R72-11268.0.0). Alternatively,
    /// postsubmit builds since R96-14175.0.0-53101 can also be specified. It is
    /// the latest version by default.
    #[argh(option)]
    version: Option<String>,

    /// the android version to push. This is passed to push_to_device.py. e.g.
    /// cheets_x86/userdebug/123456
    #[argh(option, short = 'a')]
    android_build: Option<String>,

    /// extra arguments
    #[argh(option)]
    extra_args: Vec<String>,
}

fn run_start(args: &ArgsStart) -> Result<()> {
    let mut vec = Vec::new();
    vec.append(&mut vec!["--board", &args.board]);
    if !args.reuse_disk_image {
        vec.append(&mut vec!["--reset_image"])
    }
    if let Some(display) = &args.display {
        vec.append(&mut vec!["--display", display]);
    }
    if let Some(version) = &args.version {
        vec.append(&mut vec!["--release", version]);
    }
    if let Some(android_build) = &args.android_build {
        vec.append(&mut vec!["--android_build", android_build]);
    }

    let mut options: Vec<String> = vec.iter().map(|s| s.to_string()).collect();

    let extra_args = &args.extra_args;
    options.append(&mut extra_args.clone());

    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// pushes an Android build a running betty instance
#[argh(subcommand, name = "push")]
pub struct ArgsPush {
    /// the android version to push. This is passed to push_to_device.py. e.g.
    /// cheets_x86/userdebug/123456
    #[argh(option, short = 'a')]
    android_build: String,

    /// extra arguments
    #[argh(option)]
    extra_args: Vec<String>,
}

fn run_push(args: &ArgsPush) -> Result<()> {
    let vec = ["android_build", &args.android_build];

    let mut options: Vec<String> = vec.iter().map(|s| s.to_string()).collect();

    let extra_args = &args.extra_args;
    options.append(&mut extra_args.clone());

    Ok(())
}
