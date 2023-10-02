// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::env::current_exe;
use std::fs::create_dir_all;
use std::io::ErrorKind;
use std::io::Read;
use std::path::Path;
use std::path::PathBuf;
use std::process::Command;
use std::process::Output;
use std::time::Duration;

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use async_process::Child;
use async_process::ChildStderr;
use async_process::ChildStdout;
use async_process::Stdio;
use dirs::home_dir;
use futures::io::BufReader;
use futures::io::Lines;
use futures::AsyncBufReadExt;
use wait_timeout::ChildExt;

pub fn has_root_privilege() -> Result<bool> {
    let output = run_bash_command("id -u", None)?;
    output
        .status
        .exit_ok()
        .context("Failed to get current uid")?;
    Ok(get_stdout(&output).trim() == "0")
}
/// Usage of this should be minimized, to avoid environment variable related
/// issues. Current use cases are:
/// - Resetting servo by writing to sysfs
pub fn run_lium_with_sudo(args: &[&str]) -> Result<()> {
    let mut c = Command::new("sudo");
    let status = c
        .arg("--preserve-env=HOME,PATH")
        .arg(current_exe()?)
        .args(args)
        .status()
        .context("Failed to run lium with sudo")?;
    status.exit_ok().context(anyhow!(
        "`sudo lium {} exited with {:?}`",
        args.join(" "),
        status.code()
    ))
}

pub fn lium_dir() -> Result<String> {
    gen_path_in_lium_dir(".keep").and_then(|mut path| {
        path.pop();
        Ok(path.to_str().context("Failed to get lium dir")?.to_string())
    })
}

pub fn gen_path_in_lium_dir(name: &str) -> Result<PathBuf> {
    const WORKING_DIR_NAME: &str = ".lium";

    let path = &home_dir().context("Failed to determine home dir")?;
    let path = Path::new(path);
    let path = path.join(WORKING_DIR_NAME);
    let path = path.join(name);

    let mut dir = path.clone();
    dir.pop();
    if let Err(e) = create_dir_all(&dir) {
        if e.kind() != ErrorKind::AlreadyExists {
            return Err(e).context("Failed to create a dir");
        }
    }

    Ok(path)
}

pub fn get_stdout(output: &Output) -> String {
    String::from_utf8_lossy(&output.stdout)
        .to_string()
        .trim()
        .to_string()
}
pub fn get_stderr(output: &Output) -> String {
    String::from_utf8_lossy(&output.stderr)
        .to_string()
        .trim()
        .to_string()
}
pub type AsyncLinesReader<T> = Lines<BufReader<T>>;
pub fn get_async_lines(
    child: &mut Child,
) -> (
    Option<AsyncLinesReader<ChildStdout>>,
    Option<AsyncLinesReader<ChildStderr>>,
) {
    let lines = child.stdout.take().map(|s| BufReader::new(s).lines());
    let lines_err = child.stderr.take().map(|s| BufReader::new(s).lines());
    (lines, lines_err)
}

pub fn run_bash_command(cmd: &str, dir: Option<&str>) -> Result<Output> {
    let mut c = Command::new("bash");
    let c = if let Some(dir) = dir {
        c.current_dir(dir)
    } else {
        &mut c
    };
    c.arg("-c")
        .arg(cmd)
        .output()
        .context("Failed to execute cmd")
}

pub fn run_bash_command_with_timeout(
    script: &str,
    dir: Option<&str>,
    timeout: Duration,
) -> Result<String> {
    let mut cmd = Command::new("bash");
    let cmd = if let Some(dir) = dir {
        cmd.current_dir(dir)
    } else {
        &mut cmd
    };
    let mut child = cmd
        .arg("-c")
        .arg(script)
        .stdout(Stdio::piped())
        .spawn()
        .context(anyhow!("Failed to spawn command"))?;
    let status = match child
        .wait_timeout(timeout)
        .context(anyhow!("Failed to wait on command"))?
    {
        Some(status) => status,
        None => {
            child.kill().context("Failed to kill")?;
            child.wait().context("Failed to wait after kill")?;
            return Err(anyhow!("Command timeout: {script}"));
        }
    };
    if status.success() {
        let mut stdout = String::new();
        child
            .stdout
            .context("stdout was null")?
            .read_to_string(&mut stdout)
            .context("read_to_string failed")?;
        Ok(stdout)
    } else {
        return Err(anyhow!("Command returned {status:?}: {script}"));
    }
}

pub fn run_bash_command_async(cmd: &str, dir: Option<&str>) -> Result<async_process::Child> {
    let mut c = async_process::Command::new("bash");
    let c = if let Some(dir) = dir {
        c.current_dir(dir)
    } else {
        &mut c
    };
    c.arg("-c")
        .arg(cmd)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .context("Failed to spawn bash command")
}
