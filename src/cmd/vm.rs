// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::process::Command;

use anyhow::anyhow;
use anyhow::bail;
use anyhow::Context;
use anyhow::Result;
use argh::FromArgs;
use lium::config::Config;
use whoami;

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

fn run_connect(args: &ArgsConnect) -> Result<()> {
    let cmd = Command::new("ssh")
        .arg("betty")
        .args(&args.extra_args)
        .spawn()
        .context("Failed to excute ssh")?;

    let result = cmd.wait_with_output().context("Failed to wait for ssh")?;

    if !result.status.success() {
        println!("ssh failed")
    }

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

fn run_setup(args: &ArgsSetup) -> Result<()> {
    println!("Updating packages...");
    let update_package = Command::new("sudo")
        .args(["apt", "update"])
        .spawn()
        .context("Failed to execute sudo apt update")?;
    update_package
        .wait_with_output()
        .context("Failed to wait for updating packages")?;

    println!("Enable KVM...");
    enable_kvm()?;

    println!("Installing python3-pip, python3-venv...");
    let install_python_package = Command::new("sudo")
        .args(["apt", "install", "python3-pip", "python3-venv"])
        .spawn()
        .context("Failed to execute sudo apt install")?;
    install_python_package
        .wait_with_output()
        .context("Failed to wait for installing packages")?;

    println!("Running betty.sh...");
    run_betty("setup", &args.extra_args)?;

    println!("Running gcloud auth login...");
    let gcloud_auth = Command::new("gcloud")
        .args(["auth", "login"])
        .spawn()
        .context("Failed to execute gcloud login gcloud")?;
    gcloud_auth
        .wait_with_output()
        .context("Failed to wait for gcloud auth login")?;

    Ok(())
}

fn enable_kvm() -> Result<()> {
    let username = whoami::username();

    println!("Installing kvm support...");
    let install_kvm_support = Command::new("sudo")
        .args(["apt-get", "install", "qemu-system-x86"])
        .spawn()
        .context("Failed to install kvm support")?;
    install_kvm_support
        .wait_with_output()
        .context("Failed to wait for installing kvm support")?;

    println!("Load Kernel modules...");
    let load_kernel_module = Command::new("sudo")
        .args(["modprobe", "kvm-intel"])
        .spawn()
        .context("Failed to load kernel modules")?;
    load_kernel_module
        .wait_with_output()
        .context("Failed to wait for loading kernel modules")?;

    println!("Adding the user to the kvm local group...");
    let add_to_kvm_group = Command::new("sudo")
        .args(["adduser", &username, "kvm"])
        .spawn()
        .context("Failed to add the user to the kvm local group")?;
    add_to_kvm_group
        .wait_with_output()
        .context("Failed to wait for adding the user to the kvm local group")?;

    let is_kvm_enable = Command::new("bash")
        .args([
            "-c",
            "[[ -e /dev/kvm ]] && grep '^flags' /proc/cpuinfo | grep -qE 'vmx|svm'",
        ])
        .status()
        .context("Failed to verify that KVM is working")?;
    if !is_kvm_enable.success() {
        bail!("KVM is not working");
    }

    println!("Give the user access to /dev/kvm...");
    let set_access = Command::new("sudo")
        .args(["setfacl", "-m", &format!("u:{}:rw", username), "/dev/kvm"])
        .spawn()
        .context("Failed to execute setfacl")?;
    set_access
        .wait_with_output()
        .context("Failed to wait for setting access")?;

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

    run_betty("start", &options)
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

    run_betty("push", &options)
}

fn run_betty(subcommand: &str, options: &[String]) -> Result<()> {
    let cmd = Command::new("./betty.sh")
        .arg(subcommand)
        .args(options)
        .spawn()
        .context("Failed to execute betty.sh")?;

    let result = cmd
        .wait_with_output()
        .context("Failed to wait for betty.sh")?;

    if !result.status.success() {
        println!("betty.sh failed")
    }

    Ok(())
}
