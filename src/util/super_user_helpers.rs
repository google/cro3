use std::env::current_exe;
use std::process::Command;

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;

use super::shell_helpers;

pub fn has_root_privilege() -> Result<bool> {
    let output = shell_helpers::run_bash_command("id -u", None)?;
    output
        .status
        .exit_ok()
        .context("Failed to get current uid")?;
    Ok(shell_helpers::get_stdout(&output).trim() == "0")
}

/// Usage of this should be minimized, to avoid environment variable related
/// issues. Current use cases are:
/// - Resetting servo by writing to sysfs
pub fn run_cro3_with_sudo(args: &[&str]) -> Result<()> {
    let mut c = Command::new("sudo");
    let status = c
        .arg("--preserve-env=HOME,PATH")
        .arg(current_exe()?)
        .args(args)
        .status()
        .context("Failed to run cro3 with sudo")?;
    status.exit_ok().context(anyhow!(
        "`sudo cro3 {} exited with {:?}`",
        args.join(" "),
        status.code()
    ))
}
