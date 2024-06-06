// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::path::PathBuf;
use std::ffi::OsStr;
use std::path::Path;

use anyhow::anyhow;
use anyhow::bail;
use anyhow::Context;
use anyhow::Result;
use async_process::Child;
use futures::executor::block_on;
use futures::select;
use futures::stream;
use futures::StreamExt;
use glob::Pattern;
use tracing::warn;
use tracing::info;
use std::fs::read_dir;

use crate::cache::KvCache;
use crate::chroot::Chroot;
use crate::config::Config;
use crate::cros::ensure_testing_rsa_is_there;
use crate::dut::SshInfo;
use crate::repo::get_cros_dir;
use crate::util::shell_helpers::get_async_lines;
use crate::util::shell_helpers::run_bash_command_async;

#[derive(Debug)]
pub enum TastTestExecutionType {
    Chroot(Chroot),
    TastPack(PathBuf),
}
impl TastTestExecutionType {
    pub fn from_cros_or_tastpack(cros: Option<&str>, tastpack: Option<&str>) -> Result<Self> {
        match (cros, tastpack) {
            (Some(cros), None) => {
                let repodir = get_cros_dir(Some(cros))?;
                let chroot = Chroot::new(&repodir)?;
                Ok(TastTestExecutionType::Chroot(chroot))
            }
            (None, Some(tastpack)) => Ok(TastTestExecutionType::TastPack(PathBuf::from(tastpack))),
            _ => {
                warn!(
                    "Neither --cros nor --tastpack is specified. Trying to use the current \
                     directory as a Chroot..."
                );
                (|| -> Result<TastTestExecutionType> {
                    let repodir = get_cros_dir(None)?;
                    let chroot = Chroot::new(&repodir)?;
                    Ok(TastTestExecutionType::Chroot(chroot))
                })()
                .context("Please specify either --cros or --tastpack")
            }
        }
    }
}

pub static TEST_CACHE: KvCache<Vec<String>> = KvCache::new("tast_cache");
pub static DEFAULT_BUNDLE: &str = "cros";

pub fn print_cached_tests_in_bundle(filter: &Pattern, bundle: &str) -> Result<()> {
    if let Ok(Some(tests)) = TEST_CACHE.get(bundle) {
        for t in &tests {
            if filter.matches(t) {
                println!("{t}");
            }
        }
        return Ok(());
    }
    bail!("No cache found")
}

pub fn print_cached_tests(filter: &Pattern, bundles: &Vec<&str>) -> Result<()> {
    // Ensure all bundles are cached.
    for b in bundles {
        if TEST_CACHE.get(b)?.is_none() {
            bail!("No cache found for {b}.");
        }
    }
    for b in bundles {
        print_cached_tests_in_bundle(filter, b)?
    }
    Ok(())
}

pub fn update_cached_tests_in_bundle(bundle: &str, chroot: &Chroot, port: u16) -> Result<()> {
    let list = chroot.exec_in_chroot(&[
        "tast",
        "list",
        "-installbuilddeps",
        &format!("--buildbundle={}", bundle),
        &format!("127.0.0.1:{}", port),
    ])?;
    let tests: Vec<String> = list.lines().map(|s| s.to_string()).collect::<Vec<_>>();
    TEST_CACHE.set(bundle, tests)?;
    Ok(())
}

pub fn update_cached_tests(bundles: &Vec<&str>, dut: &str, repodir: &str) -> Result<()> {
    ensure_testing_rsa_is_there()?;
    let chroot = Chroot::new(repodir)?;
    let ssh = SshInfo::new(dut).context("failed to create SshInfo")?;
    let ssh = ssh.into_forwarded()?;
    let ssh = ssh.ssh();

    // To avoid "build failed: failed checking build deps:" error
    chroot.run_bash_script_in_chroot("update_board_chroot", "update_chroot", None)?;

    for b in bundles {
        update_cached_tests_in_bundle(b, &chroot, ssh.port())?
    }
    Ok(())
}

fn bundle_has_test(bundle: &str, filter: &Pattern) -> bool {
    if let Ok(Some(tests)) = TEST_CACHE.get(bundle) {
        for t in tests {
            if filter.matches(&t) {
                return true;
            }
        }
    }
    false
}

pub async fn monitor_and_await_tast_execution(mut child: Child) -> Result<()> {
    let (so, se) = get_async_lines(&mut child);
    let so = so.context(anyhow!("ssh_stdout was None"))?;
    let se = se.context(anyhow!("ssh_stderr was None"))?;
    let mut merged_stream = stream::select(se.fuse(), so.fuse());
    let mut num_lines = 0;
    let mut num_network_diagnosis = 0;
    loop {
        let mut merged_stream = merged_stream.next();
        select! {
            line = merged_stream => {
                if let Some(Ok(line)) = line {
                    // Using eprintln!() instead of info!() to reduce the headers
                    eprintln!("{line}");
                    if line.contains("Running network diagnosis") {
                        num_network_diagnosis += 1;
                    }
                    num_lines += 1;
                    if num_lines % 100 == 0 {
                        num_network_diagnosis = 0;
                    }
                    if num_network_diagnosis > 5 {
                        bail!("network diagnosi burst detected. terminating the test...");
                    }
                }
            }
            complete => {
                // stdout is closed unexpectedly since ssh process is terminated.
                // stderr may contain some info and will be closed as well,
                // so do nothing here and wait for activities on stderr stream.
                break;
            }
        }
    }
    Ok(())
}

pub fn run_test_with_bundle(
    bundle: &str,
    filter: &Pattern,
    tast: &TastTestExecutionType,
    port: u16,
    opt: Option<&str>,
) -> Result<()> {
    match tast {
        TastTestExecutionType::Chroot(chroot) => {
            chroot.run_bash_script_in_chroot(
                "tast_run_cmd",
                &format!(
                    "tast run -installbuilddeps -buildbundle={bundle} {} 127.0.0.1:{port} {filter}",
                    opt.unwrap_or("")
                ),
                None,
            )?;
        }
        TastTestExecutionType::TastPack(path) => {
            let mut path = path.clone();
            path.push("run_tast.sh");
            let path = path.as_os_str().to_string_lossy();
            let output = run_bash_command_async(
                &format!("{path} {} 127.0.0.1:{port} {filter}", opt.unwrap_or("")),
                None,
            )?;
            block_on(monitor_and_await_tast_execution(output))?;
        }
    }
    Ok(())
}

pub fn run_tast_test(
    ssh: &SshInfo,
    tast: &TastTestExecutionType,
    test_query: &str,
    tast_options: Option<&str>,
) -> Result<()> {
    ensure_testing_rsa_is_there()?;
    let ssh = ssh.into_forwarded()?;
    let ssh = ssh.ssh();
    let filter = Pattern::new(test_query)?;

    let mut matched = false;
    let config = Config::read()?;
    let mut bundles = config.tast_bundles();
    if bundles.is_empty() {
        bundles.push(DEFAULT_BUNDLE);
    }

    for b in bundles {
        if bundle_has_test(b, &filter) {
            matched = true;
            run_test_with_bundle(b, &filter, tast, ssh.port(), tast_options)?
        }
    }

    if !matched {
        warn!("{test_query} did not match any cached tests. Run it with default bundle.");
        run_test_with_bundle(DEFAULT_BUNDLE, &filter, tast, ssh.port(), tast_options)?
    }

    Ok(())
}

pub fn collect_results(cros: Option<&str>, results_dir: Option<&str>, start: Option<&str>, end: Option<&str>) -> Result<Vec<PathBuf>> {
    let results_dir = match (&cros, &results_dir) {
        (Some(cros), None) => {
            let cros = Path::new(cros);
            if !cros.is_dir() {
                bail!("{cros:?} is not a dir");
            }
            cros.join("out").join("tmp").join("tast").join("results")
        }
        (None, Some(results_dir)) => Path::new(results_dir).to_path_buf(),
        _ => {
            bail!("Please specify --cros xor --results-dir")
        }
    };
    if !results_dir.is_dir() {
        bail!("{results_dir:?} is not a dir");
    }
    let mut results: Vec<PathBuf> = read_dir(&results_dir)?
        .flatten()
        .map(|e| e.path().to_path_buf())
        .collect();
    results.sort();
    info!("{} test results found", results.len());
    let start = start.map(OsStr::new);
    let end = end.map(OsStr::new);
    let results: Vec<PathBuf> = results
        .iter()
        .filter(|f| -> bool {
            if let Some(f) = f.file_name() {
                match (start, end) {
                    (Some(start), None) => start <= f,
                    (Some(start), Some(end)) => start <= f && f <= end,
                    (None, Some(end)) => f <= end,
                    (None, None) => true
                }
            } else {
                false
            }
        })
        .cloned()
        .collect();
    info!("{} test results in the specified range", results.len());

    Ok(results)
}
