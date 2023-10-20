use std::io::Read;
use std::process::Command;
use std::process::Output;
use std::time::Duration;

use anyhow::anyhow;
use anyhow::bail;
use anyhow::Context;
use anyhow::Result;
use async_process::Child;
use async_process::ChildStderr;
use async_process::ChildStdout;
use async_process::Stdio;
use futures::io::BufReader;
use futures::io::Lines;
use futures::AsyncBufReadExt;
use wait_timeout::ChildExt;

pub fn get_stdout(output: &Output) -> String {
    String::from_utf8_lossy(&output.stdout).trim().to_string()
}

pub fn get_stderr(output: &Output) -> String {
    String::from_utf8_lossy(&output.stderr).trim().to_string()
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
            bail!("Command timeout: {script}");
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
        bail!("Command returned {status:?}: {script}")
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
