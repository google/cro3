// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::env;
use std::path::Path;
use std::process::Command;
use std::string::ToString;

use anyhow::anyhow;
use anyhow::bail;
use anyhow::Context;
use anyhow::Result;
use argh::FromArgs;
use lium::config::Config;
use lium::util::shell_helpers::run_bash_command;
use regex_macro::regex;
use strum_macros::Display;
use tracing::error;
use tracing::info;
use whoami;

#[derive(FromArgs, PartialEq, Debug)]
/// create a virtual machine
#[argh(subcommand, name = "vm")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}

#[derive(FromArgs, PartialEq, Debug, Display)]
#[argh(subcommand)]
enum SubCommand {
    #[strum(serialize = "setup")]
    Setup(ArgsSetup),

    #[strum(serialize = "start")]
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

#[derive(Clone, FromArgs, PartialEq, Debug)]
/// for betty.sh. Run first time setup, installs necessary dependencies.
#[argh(subcommand, name = "setup")]
pub struct ArgsSetup {
    /// path to the android source checkout. If omitted, current directory will
    /// be used.
    #[argh(option)]
    arc: Option<String>,

    /// extra arguments to pass to betty.sh. You can pass other options like
    /// --extra-args "options".
    #[argh(option)]
    extra_args: Option<String>,
}

fn run_setup(args: &ArgsSetup) -> Result<()> {
    let dir = find_betty_script(&args.arc)?;

    info!("Updating packages...");
    let mut update_package = Command::new("sudo")
        .args(["apt", "update"])
        .spawn()
        .context("Failed to execute sudo apt update")?;
    update_package
        .wait()
        .context("Failed to wait for updating packages")?;

    info!("Enabling KVM...");
    enable_kvm()?;

    info!("Installing python packages...");
    let mut install_python_package = Command::new("sudo")
        .args(["apt", "install", "python3-pip", "python3-venv"])
        .spawn()
        .context("Failed to install python packages")?;
    install_python_package
        .wait()
        .context("Failed to wait for installing python packages")?;

    info!("Running betty.sh setup...");
    let options = args.extra_args.clone().unwrap_or_else(|| String::from(""));
    run_betty_cmd(&dir, SubCommand::Setup(args.clone()), &[&options])?;

    info!("Running gcloud auth login...");
    let mut gcloud_auth = Command::new("gcloud")
        .args(["auth", "login"])
        .spawn()
        .context("Failed to run gcloud login gcloud")?;
    gcloud_auth
        .wait()
        .context("Failed to wait for gcloud auth login")?;

    Ok(())
}

fn enable_kvm() -> Result<()> {
    info!("Installing kvm support...");
    let mut install_kvm_support = Command::new("sudo")
        .args(["apt-get", "install", "qemu-system-x86"])
        .spawn()
        .context("Failed to install kvm support")?;
    install_kvm_support
        .wait()
        .context("Failed to wait for installing kvm support")?;

    let is_intel = run_bash_command("grep vmx /proc/cpuinfo", None)?
        .status
        .success();
    let is_amd = run_bash_command("grep svm /proc/cpuinfo", None)?
        .status
        .success();
    let module = if is_intel {
        "kvm-intel"
    } else if is_amd {
        "kvm-amd"
    } else {
        bail!("Your system does not have virtualization extensions.");
    };

    info!("Loading Kernel modules...");
    let mut load_kernel_module = Command::new("sudo")
        .args(["modprobe", module])
        .spawn()
        .context("Failed to load kernel modules")?;
    load_kernel_module
        .wait()
        .context("Failed to wait for loading kernel modules")?;

    let username = whoami::username();
    info!("Adding the user to the kvm local group...");
    let mut add_to_kvm_group = Command::new("sudo")
        .args(["adduser", &username, "kvm"])
        .spawn()
        .context("Failed to add the user to the kvm local group")?;
    add_to_kvm_group
        .wait()
        .context("Failed to wait for adding the user to the kvm local group")?;

    let is_kvm_enabled = run_bash_command(
        "[[ -e /dev/kvm ]] && grep '^flags' /proc/cpuinfo | grep -qE 'vmx|svm'",
        None,
    )?
    .status
    .success();

    if !is_kvm_enabled {
        bail!("KVM did not enable correctly");
    }

    info!("Setting the user access to /dev/kvm...");
    let mut set_access = Command::new("sudo")
        .args(["setfacl", "-m", &format!("u:{}:rw", username), "/dev/kvm"])
        .spawn()
        .context("Failed to set access to /dev/kvm")?;
    set_access
        .wait()
        .context("Failed to wait for setting access to /dev/kvm")?;

    Ok(())
}

#[derive(Clone, FromArgs, PartialEq, Debug)]
/// start a betty VM instance
#[argh(subcommand, name = "start")]
pub struct ArgsStart {
    /// for betty.sh. Path to the android source checkout. If omitted, current
    /// directory will be used.
    #[argh(option)]
    arc: Option<String>,

    /// for betty.sh. The BOARD to run (e.g. betty-pi-arc). It is required when
    /// you launch a local VM instance.
    #[argh(option)]
    board: Option<String>,

    /// for betty.sh. Reuse the VM image. It is true by default. If you want to
    /// disable it, use `--reuse-disk-image false`.
    #[argh(option, default = "true")]
    reuse_disk_image: bool,

    /// for betty.sh. Start betty with rootfs verification. It is false by
    /// default.
    #[argh(switch)]
    enable_rootfs_verification: bool,

    /// for betty.sh. The ChromeOS version to use (e.g. R72-11268.0.0).
    /// Alternatively, postsubmit builds since R96-14175.0.0-53101 can also
    /// be specified. It is the latest version by default.
    #[argh(option)]
    version: Option<String>,

    /// for betty.sh. Path to betty VM image to start. It has priority over
    /// --board and --version (they will be ignored)
    #[argh(option)]
    vm_image: Option<String>,

    /// for acloudw. Launch a cloud based VM instance. It is false by default.  
    #[argh(switch)]
    acloud: bool,

    /// for acloudw. The Android branch. It is required if --acloud is
    /// specified.
    #[argh(option)]
    branch: Option<String>,

    /// for acloudw. The Android Build ID. It is required if --acloud is
    /// specified.
    #[argh(option)]
    build_id: Option<String>,

    /// for acloudw. Select ARC-container, not ARCVM. It is false by default.
    #[argh(switch)]
    container: bool,

    /// extra arguments to pass to betty.sh or acloudw. You can pass other
    /// options like --extra-args "options".
    #[argh(option)]
    extra_args: Option<String>,
}

fn run_start(args: &ArgsStart) -> Result<()> {
    if args.acloud {
        run_acloudw(args)?;
    } else {
        run_betty_start(args)?;

        println!("To connect the betty instance, run `lium dut shell --dut localhost:9222`.");
        println!("To push an Android build a betty VM, run `lium arc flash`.");
    }

    Ok(())
}

fn run_acloudw(args: &ArgsStart) -> Result<()> {
    let branch = args
        .branch
        .clone()
        .ok_or(anyhow!("--branch option is required when using acloudw"))?;
    let git_branch = format!("git_{branch}");

    // b/314731302 use the Android API to get this programmatically if not specified
    let build_id = args
        .build_id
        .clone()
        .ok_or(anyhow!("--build-id option is required when using acloudw"))?;
    let re = regex!(r"^\d+$");
    if !re.is_match(&build_id) {
        bail!("--build-id must be a digit.");
    }

    let config = Config::read()?;

    let cmd_path = config.acloudw_cmd_path().context(
        "Config acloudw_cmd_path is required when using acloudw. For internal users, please \
         configure path to acloudw.sh",
    )?;
    let config_path = config.acloudw_config_path().context(
        "Config acloudw_config_path is required when using acloudw. For internal users, please \
         configure path to acloudw config file",
    )?;
    let target = get_target_name(&config, args.container, &branch)?;
    let cheeps = get_cheeps_image_name(&config, args.container, &branch)?;
    let betty = get_betty_image_name(&config, args.container, &branch)?;

    let mut options = vec![
        &cmd_path,
        "create",
        "--avd-type cheeps",
        "--branch",
        &git_branch,
        "--build-id",
        &build_id,
        "--config-file",
        &config_path,
        "--build-target",
        &target,
        "--stable-cheeps-host-image-name",
        &cheeps,
        &betty,
    ];

    if let Some(extra_args) = &args.extra_args {
        options.extend_from_slice(&[extra_args]);
    }

    run_acloudw_cmd(&options)
}

fn get_target_name(config: &Config, is_container: bool, branch: &str) -> Result<String> {
    let vm_type = if branch.contains("main") {
        "main"
    } else if is_container {
        "container"
    } else {
        "vm"
    };

    Ok(config
        .android_target_for_vm_type()
        .get(vm_type)
        .context(
            "Config android_target is required when using acloudw. For internal users, please \
             configure lunch target name",
        )?
        .to_string())
}

fn get_betty_image_name(config: &Config, is_container: bool, branch: &str) -> Result<String> {
    if is_container {
        return Ok("".to_string());
    }
    let cmd = config
        .arc_vm_betty_image_for_branch()
        .get(branch)
        .context(
            "Config arc_vm_betty_image is not set. For internal users, please configure betty \
             image name",
        )?
        .to_string();
    let betty = String::from_utf8(run_bash_command(&cmd, None)?.stdout)?;

    Ok(format!("--betty-image {betty} --boot-timeout 720"))
}

fn get_cheeps_image_name(config: &Config, is_container: bool, branch: &str) -> Result<String> {
    let cmd = if is_container {
        config
            .arc_container_cheeps_image_for_branch()
            .get(branch)
            .context(
                "Config arc_container_cheeps_image is not set. For internal users, please \
                 configure cheeps image name for ARCVM",
            )?
            .to_string()
    } else {
        config.arc_vm_cheeps_image().context(
            "Config arc_vm_cheeps_image is not set. For internal users, please configure cheeps \
             image name for ARC-Container",
        )?
    };
    let cheeps = String::from_utf8(run_bash_command(&cmd, None)?.stdout)?;

    Ok(cheeps)
}

fn run_acloudw_cmd(opts: &[&str]) -> Result<()> {
    let config = Config::read()?;
    let auth_valid_cmd = config
        .is_internal_auth_valid()
        .context("Config is_internal_auth_valid is required when using acloudw.")?;

    info!("Running `{auth_valid_cmd}`...");
    let is_internal_auth_valid = run_bash_command(&auth_valid_cmd, None)?;
    if !is_internal_auth_valid.status.success() {
        bail!("{:#?}", is_internal_auth_valid);
    }

    let acloudw_cmd = opts.join(" ");
    info!("Running `{acloudw_cmd}`...");
    let mut cmd = Command::new("bash")
        .arg("-c")
        .arg(acloudw_cmd)
        .spawn()
        .context("Failed to execute acloudw")?;

    let result = cmd.wait().context("Failed to wait for acloudw")?;

    if !result.success() {
        error!("acloudw failed")
    }

    Ok(())
}

fn run_betty_start(args: &ArgsStart) -> Result<()> {
    let dir = find_betty_script(&args.arc)?;

    let board = args
        .board
        .clone()
        .ok_or(anyhow!("--board option is required when using betty.sh"))?;

    let mut options = vec!["--board", &board, "--display", "none"];

    if !args.reuse_disk_image {
        options.extend_from_slice(&["--reset_image"]);
    }
    if args.enable_rootfs_verification {
        options.extend_from_slice(&["--nodisbple_rootfs"]);
    }
    if let Some(version) = &args.version {
        options.extend_from_slice(&["--release", version]);
    }
    if let Some(vm_image) = &args.vm_image {
        options.extend_from_slice(&["--vm_image", vm_image]);
    }
    if let Some(extra_args) = &args.extra_args {
        options.extend_from_slice(&[extra_args]);
    }

    run_betty_cmd(&dir, SubCommand::Start(args.clone()), &options)
}

fn find_betty_script(arc: &Option<String>) -> Result<String> {
    let path_to_android = arc
        .clone()
        .unwrap_or_else(|| env::current_dir().unwrap().to_string_lossy().to_string());
    let path_to_arc = Path::new(&path_to_android).join("tools/vendor/google_prebuilts/arc");

    if Path::new(&path_to_arc).join("betty.sh").exists() {
        return Ok(path_to_arc.to_string_lossy().to_string());
    }

    bail!("betty.sh doesn't exist in {path_to_android}. Please consider specifying --arc option.")
}

fn run_betty_cmd(dir: &str, cmd: SubCommand, opts: &[&str]) -> Result<()> {
    let betty_cmd = format!("./betty.sh {} {}", cmd, opts.join(" "));
    info!("Running `{betty_cmd}`...");
    let mut cmd = Command::new("bash")
        .current_dir(dir)
        .arg("-c")
        .arg(betty_cmd)
        .spawn()
        .context("Failed to execute betty.sh")?;

    let result = cmd.wait().context("Failed to wait for betty.sh")?;

    if !result.success() {
        error!("betty.sh failed")
    }

    Ok(())
}
