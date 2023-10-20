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
use tracing::trace;
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
    launch_command_with_stdout_label_and_process::<fn(_) -> _>(
        c,
        attempted_command_name_summary,
        None,
    )
}

/// An iterator container for stdout and stderr that will always pull the next
/// values even if unused, so that the process can continue.
///
/// Without this, the process will block if the stdout or stderr is not read.
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
    F: FnOnce(CommandOutputReciever) -> Result<()>,
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
    let join = spawn_output_reader_thread(stdout_iter, stderr_iter, stdout_snd, stderr_snd);

    // Read the recieving ends of the channels and pass them to the process
    // function's input.
    if let Some(process) = process {
        // create a tracing span for the process function.
        let _process_span = tracing::trace_span!("process stdout/err").entered();

        process(CommandOutputReciever::new(
            stdout_rcv.into_iter(),
            stderr_rcv.into_iter(),
        ))?;
    }

    // Wait for the process to finish, then wait for the thread to finish reading
    // stdout/err.
    let r = child.wait()?;
    info!("Subprocess {executable} finished with exit code {r}");

    join.join()
        .map_err(|e| anyhow!("could not join stdout/err logging and copy thread: {e:?}"))?;
    trace!("stdout/err logging and copy thread joined");

    Ok(r)
}

/// This function creates a thread that reads the stdout and stderr of a sub
/// command and logs them, forwarding a copy to the channels.
///
/// This is a little complex because in order to continue with a fixed size
/// channel, once one is exhausted it needs to be closed. This is why instead of
/// a single for loop over the iterator, there is a while let until one of
/// stdout or stderr is exhausted, then the corresponding channel is closed and
/// the other is drained.
fn spawn_output_reader_thread<IOut, IErr>(
    stdout_iter: IOut,
    stderr_iter: IErr,
    stdout_snd: std::sync::mpsc::SyncSender<String>,
    stderr_snd: std::sync::mpsc::SyncSender<String>,
) -> std::thread::JoinHandle<()>
where
    IOut: Iterator<Item = std::io::Result<String>> + Send + 'static,
    IErr: Iterator<Item = std::io::Result<String>> + Send + 'static,
{
    std::thread::spawn(move || {
        let _stdout_stderr_output_reader_span =
            tracing::trace_span!("subprocess output reader").entered();

        // Iterate until one of stdout or stderr is exhausted.
        let mut cmd_outputs_iter = stdout_iter.zip_longest(stderr_iter);
        let mut curr = cmd_outputs_iter.next();
        while let Some(EitherOrBoth::Both(stdout, stderr)) = curr {
            let stdout = stdout.unwrap();
            let stderr = stderr.unwrap();
            info!("{}", stdout.clone());
            stdout_snd.send(stdout).unwrap();

            info!("stderr: {}", stderr.clone());
            stderr_snd.send(stderr).unwrap();

            curr = cmd_outputs_iter.next();
        }

        // Close the corresponding channel, and drain the other iterator.
        match curr {
            Some(EitherOrBoth::Left(_)) => {
                drop(stderr_snd);
                while let Some(EitherOrBoth::Left(stdout)) = cmd_outputs_iter.next() {
                    let stdout = stdout.unwrap();
                    info!("{}", stdout.clone());
                    stdout_snd.send(stdout).unwrap();
                }
            }
            Some(EitherOrBoth::Right(_)) => {
                drop(stdout_snd);
                while let Some(EitherOrBoth::Right(stderr)) = cmd_outputs_iter.next() {
                    let stderr = stderr.unwrap();
                    info!("stderr: {}", stderr.clone());
                    stderr_snd.send(stderr).unwrap();
                }
            }
            Some(EitherOrBoth::Both(_, _)) => panic!("somehow a stdout or stderr came back alive!"),
            None => (), // We're done.
        }
    })
}

pub struct CommandOutputReciever {
    stdout_iter: std::sync::mpsc::IntoIter<String>,
    stderr_iter: std::sync::mpsc::IntoIter<String>,
}

pub struct CommandOutputStdOutReciever {
    command_output_reciever: CommandOutputReciever,
}

pub struct CommandOutputStdErrReciever {
    command_output_reciever: CommandOutputReciever,
}

impl CommandOutputReciever {
    fn new(
        stdout_iter: std::sync::mpsc::IntoIter<String>,
        stderr_iter: std::sync::mpsc::IntoIter<String>,
    ) -> Self {
        Self {
            stdout_iter,
            stderr_iter,
        }
    }

    pub fn stdout_only(self) -> CommandOutputStdOutReciever {
        CommandOutputStdOutReciever {
            command_output_reciever: self,
        }
    }

    pub fn stderr_only(self) -> CommandOutputStdErrReciever {
        CommandOutputStdErrReciever {
            command_output_reciever: self,
        }
    }
}

impl Iterator for CommandOutputReciever {
    type Item = (Option<String>, Option<String>);

    fn next(&mut self) -> Option<Self::Item> {
        let stdout = self.stdout_iter.next();
        let stderr = self.stderr_iter.next();
        if stdout.is_some() || stderr.is_some() {
            return Some((stdout, stderr));
        }

        None
    }
}

impl Iterator for CommandOutputStdOutReciever {
    type Item = String;

    fn next(&mut self) -> Option<Self::Item> {
        let (stdout, _) = self.command_output_reciever.next()?;

        if stdout.is_none() {
            // Exhaust the iterator and return None.
            for _ in self.command_output_reciever.by_ref() {}
            return None;
        }

        stdout
    }
}

impl Iterator for CommandOutputStdErrReciever {
    type Item = String;

    fn next(&mut self) -> Option<Self::Item> {
        let (_, stderr) = self.command_output_reciever.next()?;

        if stderr.is_none() {
            // Exhaust the iterator and return None.
            for _ in self.command_output_reciever.by_ref() {}
            return None;
        }

        stderr
    }
}
