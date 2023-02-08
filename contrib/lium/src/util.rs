// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

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
use std::env;
use std::env::current_exe;
use std::fs::create_dir_all;
use std::io::ErrorKind;
use std::path::Path;
use std::path::PathBuf;
use std::process::Command;
use std::process::Output;

pub fn require_root_privilege() -> Result<()> {
    let output = run_bash_command("id -u", None)?;
    output.status.exit_ok()?;
    if get_stdout(&output).trim() == "0" {
        Ok(())
    } else {
        eprintln!("This actions requires root permission. Restarting with sudo...");
        let mut c = Command::new("sudo");
        let args: Vec<String> = env::args().into_iter().skip(1).collect();
        std::process::exit(
            c.arg(current_exe()?)
                .args(&args)
                .status()
                .context("Failed to re-execute lium with sudo")?
                .code()
                .expect("Exit code is not available"),
        )
    }
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
pub fn get_async_lines(
    child: &mut Child,
) -> (Lines<BufReader<ChildStdout>>, Lines<BufReader<ChildStderr>>) {
    let lines = BufReader::new(child.stdout.take().unwrap()).lines();
    let lines_err = BufReader::new(child.stderr.take().unwrap()).lines();
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
