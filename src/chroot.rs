// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::fs;
use std::process::Command;
use std::process::Stdio;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use signal_hook::consts::SIGINT;
use tracing::error;
use tracing::info;

use crate::util::cro3_paths::cro3_dir;
use crate::util::cro3_paths::gen_path_in_cro3_dir;
use crate::util::shell_helpers::get_stderr;
use crate::util::shell_helpers::get_stdout;
use crate::util::shell_helpers::run_bash_command;

#[derive(Debug)]
pub struct Chroot {
    repo_path: String,
}
impl Chroot {
    pub fn new(repo_path: &str) -> Result<Self> {
        let chroot = Chroot {
            repo_path: repo_path.to_string(),
        };
        let cro3_dir_path = cro3_dir()?;
        info!("Using Chromium OS checkout at {}", repo_path);
        run_bash_command(
            &format!(
                "echo {0} /cro3 > {1} && cat {1}",
                cro3_dir_path, "src/scripts/.local_mounts"
            ),
            Some(repo_path),
        )?
        .status
        .exit_ok()?;
        // Remove ~/.bash_logout in chroot to avoid clearing the screen after exiting
        // Ignore error
        drop(chroot.run_bash_script_in_chroot("remove_bash_logout", "rm -f ~/.bash_logout", None));
        Ok(chroot)
    }
    pub fn exec_in_chroot(&self, args: &[&str]) -> Result<String> {
        let mut cmd = Command::new("cros_sdk");
        cmd.arg("--no-ns-pid")
            .arg("--")
            .args(args)
            .current_dir(&self.repo_path)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        info!("in chroot: {:?}", cmd);
        let cmd = cmd.spawn()?;
        let result = cmd.wait_with_output()?;
        result
            .status
            .exit_ok()
            .context(anyhow!("exec_in_chroot failed: {}", get_stderr(&result)))?;
        let result = get_stdout(&result);
        Ok(result)
    }
    pub fn exec_in_chroot_async(&self, args: &[&str]) -> Result<async_process::Child> {
        let mut cmd = async_process::Command::new("bash");
        let cmd = cmd
            .arg("-c")
            .arg("cros_sdk --no-ns-pid -- ".to_string() + &args.join(" "))
            .current_dir(&self.repo_path)
            .kill_on_drop(true)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        info!("Executing: {cmd:?} async");
        cmd.spawn().context("exec_in_chroot_async failed")
    }
    pub fn write_bash_script_for_chroot(&self, name: &str, script: &str) -> Result<()> {
        let dst = gen_path_in_cro3_dir(&format!("tmp/{name}.sh"))?;
        fs::write(dst, script.as_bytes()).context("Failed to create a script file")?;
        Ok(())
    }
    /// Run a script in chroot.
    ///
    /// # Arguments
    ///
    /// * `name` - A filename-capable identifier for the script (this file will
    ///   be created automatically)
    /// * `script` - One or more lines of bash script
    /// * `args` - args to be passed to the script
    pub fn run_bash_script_in_chroot(
        &self,
        name: &str,
        script: &str,
        args: Option<&[&str]>,
    ) -> Result<String> {
        self.write_bash_script_for_chroot(name, script)?;
        let mut cmd = Command::new("cros_sdk");
        cmd.args([
            "--no-ns-pid",
            "--",
            "bash",
            "-xe",
            &format!("/cro3/tmp/{}.sh", name),
        ])
        .current_dir(&self.repo_path)
        .stdin(Stdio::piped());
        if let Some(args) = args {
            cmd.args(args);
        }
        info!("Running {name} in chroot...");
        let run = cmd
            .spawn()
            .context(anyhow!("spawn failed. cmd = {cmd:?}"))?;

        // Hit Ctrl-C twice to terminate cro3 immediately.
        // Note that the Ctrl-C (SIGINT) will be sent to both the bash script
        // in chroot and the parent cro3 process from the terminal.
        // The bash script will (hopefully) terminates its child process but
        // it may take a while. Since cro3 will quit immediately by default
        // we need to setup SIGINT handlers to wait it.
        let intr = Arc::new(AtomicBool::new(false));
        // This will shutdown cro3 only if the 'intr' is true.
        signal_hook::flag::register_conditional_shutdown(SIGINT, 1, Arc::clone(&intr))?;
        // This will handle the first SIGINT to set the 'intr' flag true.
        signal_hook::flag::register(SIGINT, Arc::clone(&intr))?;
        // As a result, the first SIGINT set 'intr' flag true and the child bash
        // script will be terminated (but it takes a time.)
        // If user wants to quit immediately, send the 2nd SIGINT and it
        // will shutdown cro3 because 'intr' is true now.

        let result = run
            .wait_with_output()
            .context(anyhow!("wait_with_output_failed. cmd = {cmd:?}"))?;

        // Even if user does not send SIGINT twice, this will return an error.
        if intr.load(Ordering::Relaxed) {
            return Err(anyhow!("Caught a SIGINT (Ctrl+C)"));
        }
        result
            .status
            .exit_ok()
            .context(anyhow!("run_in_chroot failed. cmd = {cmd:?}"))?;
        let result = get_stdout(&result);
        Ok(result)
    }
    pub fn run_in_chroot_async(&self, script: &str) -> Result<async_process::Child> {
        async_process::Command::new("cros_sdk")
            .args(["--no-ns-pid", "--", "bash", "-xe", "-c", script])
            .current_dir(&self.repo_path)
            .kill_on_drop(true)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .context("Failed to launch servod")
    }
    pub fn open_chroot(&self, additional_args: &[String]) -> Result<()> {
        let cmd = Command::new("cros_sdk")
            .arg("--no-color")
            .args(additional_args)
            .current_dir(&self.repo_path)
            .spawn()?;
        let result = cmd.wait_with_output()?;
        if !result.status.success() {
            error!("cros sdk failed");
        }
        Ok(())
    }
}
