// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::env;
use std::path::Path;
use std::process::Command;

use anyhow::bail;
use anyhow::Context;
use anyhow::Result;
use argh::FromArgs;
use lium::config::Config;
use lium::util::shell_helpers::run_bash_command;
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
    Setup(ArgsSetup),
    Start(ArgsStart),
}

#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    let config = Config::read()?;
    if !config.is_internal() {
        bail!("vm subcommand is currently only supported for google internal use");
    }

    match &args.nested {
        SubCommand::Setup(args) => run_setup(args),
        SubCommand::Start(args) => run_start(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// run first time setup, installs necessary dependencies
#[argh(subcommand, name = "setup")]
pub struct ArgsSetup {
    /// path to dir where betty.sh exists. If omitted, current directory will be
    /// used.
    #[argh(option)]
    arc: Option<String>,

    /// extra arguments to pass to betty.sh. You can pass other options like
    /// --extra-args "options".
    #[argh(option)]
    extra_args: Option<String>,
}

fn run_setup(args: &ArgsSetup) -> Result<()> {
    let dir = find_betty_script(&args.arc)?;

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

    println!("Installing python packages...");
    let install_python_package = Command::new("sudo")
        .args(["apt", "install", "python3-pip", "python3-venv"])
        .spawn()
        .context("Failed to install python packages")?;
    install_python_package
        .wait_with_output()
        .context("Failed to wait for installing python packages")?;

    println!("Running betty.sh setup...");
    let arg = match &args.extra_args {
        Some(a) => a,
        None => "",
    };
    run_betty(&dir, "setup", arg)?;

    println!("Running gcloud auth login...");
    let gcloud_auth = Command::new("gcloud")
        .args(["auth", "login"])
        .spawn()
        .context("Failed to run gcloud login gcloud")?;
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

    println!("Loading Kernel modules...");
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

    let is_kvm_enable = run_bash_command(
        "[[ -e /dev/kvm ]] && grep '^flags' /proc/cpuinfo | grep -qE 'vmx|svm'",
        None,
    )?;
    if !is_kvm_enable.status.success() {
        bail!("KVM is not working");
    }

    println!("Setting the user access to /dev/kvm...");
    let set_access = Command::new("sudo")
        .args(["setfacl", "-m", &format!("u:{}:rw", username), "/dev/kvm"])
        .spawn()
        .context("Failed to set access to /dev/kvm")?;
    set_access
        .wait_with_output()
        .context("Failed to wait for setting access to /dev/kvm")?;

    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// start a betty VM instance
#[argh(subcommand, name = "start")]
pub struct ArgsStart {
    /// path to dir where betty.sh exists. If omitted, current directory will be
    /// used.
    #[argh(option)]
    arc: Option<String>,

    /// the BOARD to run (e.g. betty-pi-arc)
    #[argh(option)]
    board: String,

    /// reuse the VM image. It is true by default. If you want to disable it,
    /// use `--reuse-disk-image flase`.
    #[argh(option, default = "true")]
    reuse_disk_image: bool,

    /// start betty with rootfs verification
    #[argh(switch)]
    rootfs_verify: bool,

    /// the ChromeOS version to use (e.g. R72-11268.0.0). Alternatively,
    /// postsubmit builds since R96-14175.0.0-53101 can also be specified. It is
    /// the latest version by default.
    #[argh(option)]
    version: Option<String>,

    /// path to betty VM image to start. It has priority over --board and
    /// --version (they will be ignored)
    #[argh(option)]
    vm_image: Option<String>,

    /// extra arguments to pass to betty.sh. You can pass other options like
    /// --extra-args "options".
    #[argh(option)]
    extra_args: Option<String>,
}

fn run_start(args: &ArgsStart) -> Result<()> {
    let dir = find_betty_script(&args.arc)?;

    let mut options = Vec::new();
    options.append(&mut vec!["--board", &args.board]);
    if !args.reuse_disk_image {
        options.append(&mut vec!["--reset_image"]);
    }
    if args.rootfs_verify {
        options.append(&mut vec!["--nodisable_rootfs"]);
    }
    if let Some(version) = &args.version {
        options.append(&mut vec!["--release", version]);
    }
    if let Some(vm_image) = &args.vm_image {
        options.append(&mut vec!["--vm_image", vm_image]);
    }
    options.append(&mut vec!["--display", "none"]);
    if let Some(extra_args) = &args.extra_args {
        options.append(&mut vec![extra_args]);
    }

    let arg = options.join(" ");
    run_betty(&dir, "start", &arg)?;

    println!("To connect the betty instance, run `lium dut shell --dut localhost:9222`.");
    println!("To push an Android build a betty VM, run `lium arc flash`.");

    Ok(())
}

fn find_betty_script(arc: &Option<String>) -> Result<String> {
    let path = match arc {
        Some(p) => p.to_string(),
        None => env::current_dir()?.to_string_lossy().to_string(),
    };

    if Path::new(&format!("{}/betty.sh", path)).exists() {
        return Ok(path);
    }

    bail!("betty.sh doesn't exist in {path}. Please consider specifying --repo option.")
}

fn run_betty(dir: &str, cmd: &str, opts: &str) -> Result<()> {
    let betty_script = format!("./betty.sh {} {}", cmd, opts);

    let cmd = Command::new("bash")
        .current_dir(dir)
        .arg("-c")
        .arg(betty_script)
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
