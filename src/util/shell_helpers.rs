use std::io::BufRead;
use std::io::Read;
use std::iter::Iterator;
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
use async_process::ExitStatus;
use async_process::Stdio;
use futures::io::BufReader;
use futures::io::Lines;
use futures::AsyncBufReadExt;
use itertools::EitherOrBoth;
use itertools::Itertools;
use tracing::info;
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

pub fn launch_command_with_stdout_label(
    c: &mut Command,
    attempted_command_name_summary: Option<String>,
) -> Result<ExitStatus> {
    launch_command_with_stdout_label_and_process::<fn(_, _) -> _>(
        c,
        attempted_command_name_summary,
        None,
    )
}

/// Input to the process function of
/// [launch_command_with_stdout_label_and_process] which can be iterated on to
/// get the stdout and stderr of the process for processing.
pub type CommandOutputReciever = std::sync::mpsc::IntoIter<String>;

/// Launch a command surrounded by labels to make it easier to find in logs.
/// It also prepends stderr with stderr in the logs.
///
/// [process] is a function that takes a stdout and stderr line iterator.
pub fn launch_command_with_stdout_label_and_process<F>(
    c: &mut Command,
    attempted_command_name_summary: Option<String>,
    process: Option<F>,
) -> Result<ExitStatus>
where
    F: FnOnce(CommandOutputReciever, CommandOutputReciever) -> Result<()>,
{
    // Make sure to pipe stderr/out up to this process for logging.
    c.stdout(Stdio::piped()).stderr(Stdio::piped());

    // extract the executable name from the command.
    let executable = attempted_command_name_summary.unwrap_or(
        c.get_program()
            .to_str()
            .context("Failed to get program")?
            .to_string(),
    );

    info!("Launching subprocess {executable}...");

    // Spawn the process.
    let mut child = c
        .spawn()
        .context(format!("Failed to execute {executable}"))?;

    // Read in the stdout of the process, prepend it, and forward it to our logging.
    let stdout_iter = child
        .stdout
        .take()
        .map(|s| std::io::BufReader::new(s).lines())
        .into_iter()
        .flatten();
    let stderr_iter = child
        .stderr
        .take()
        .map(|s| std::io::BufReader::new(s).lines())
        .into_iter()
        .flatten();

    // Create channels to copy the stdout and stderr to.
    let (stdout_snd, stdout_rcv) = std::sync::mpsc::sync_channel(1);
    let (stderr_snd, stderr_rcv) = std::sync::mpsc::sync_channel(1);
    let join = std::thread::spawn(move || {
        for pair in stdout_iter.zip_longest(stderr_iter) {
            match pair {
                EitherOrBoth::Both(stdout, stderr) => {
                    let stdout = stdout.unwrap();
                    let stderr = stderr.unwrap();
                    info!("{}", stdout.clone());
                    stdout_snd.send(stdout).unwrap();

                    info!("stderr: {}", stderr.clone());
                    stderr_snd.send(stderr).unwrap();
                }
                EitherOrBoth::Left(stdout) => {
                    let stdout = stdout.unwrap();
                    info!("{}", stdout.clone());
                    stdout_snd.send(stdout).unwrap();
                }
                EitherOrBoth::Right(stderr) => {
                    let stderr = stderr.unwrap();
                    info!("stderr: {}", stderr.clone());
                    stderr_snd.send(stderr).unwrap();
                }
            }
        }
    });

    // Read the recieving ends of the channels and pass them to the process
    // function's input.
    if let Some(process) = process {
        let stdout_iter = stdout_rcv.into_iter();
        let stderr_iter = stderr_rcv.into_iter();
        process(stdout_iter, stderr_iter)?;
    }

    join.join()
        .map_err(|_| anyhow!("could not join stdout/err logging and copy thread"))?;
    let r = child.wait()?;

    info!("Subprocess {executable} finished with exit code {r}");

    Ok(r)
}
