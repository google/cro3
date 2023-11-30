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
use tracing::info;

use crate::util::lium_paths::gen_path_in_lium_dir;
use crate::util::lium_paths::lium_dir;
use crate::util::shell_helpers::get_stderr;
use crate::util::shell_helpers::get_stdout;
use crate::util::shell_helpers::run_bash_command;

pub struct Chroot {
    repo_path: String,
}
impl Chroot {
    pub fn new(repo_path: &str) -> Result<Self> {
        let chroot = Chroot {
            repo_path: repo_path.to_string(),
        };
        let lium_dir_path = lium_dir()?;
        info!("Using Chromium OS checkout at {}", repo_path);
        run_bash_command(
            &format!(
                "echo {0} /lium > {1} && cat {1}",
                lium_dir_path, "src/scripts/.local_mounts"
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
        let dst = gen_path_in_lium_dir(&format!("tmp/{name}.sh"))?;
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
            &format!("/lium/tmp/{}.sh", name),
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

        // Double Ctrl+C to terminal lium immediately.
        let intr = Arc::new(AtomicBool::new(false));
        signal_hook::flag::register_conditional_shutdown(SIGINT, 1, Arc::clone(&intr))?;
        signal_hook::flag::register(SIGINT, Arc::clone(&intr))?;

        let result = run
            .wait_with_output()
            .context(anyhow!("wait_with_output_failed. cmd = {cmd:?}"))?;

        if intr.load(Ordering::Relaxed) {
            return Err(anyhow!("Cought a SIGINT (Ctrl+C)"));
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
            println!("cros sdk failed");
        }
        Ok(())
    }
}
