// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

/*
cargo run --release -- abtest analyze --list-duts --results-dir /data/tast/results
*/

use std::collections::HashMap;
use std::collections::HashSet;
use std::ffi::OsStr;
use std::fs::read_dir;
use std::fs::File;
use std::io::Write;
use std::path::Path;
use std::path::PathBuf;

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
use once_cell::sync::Lazy;
use regex::Regex;
use serde::Deserialize;
use serde::Serialize;
use tracing::info;
use tracing::warn;

use crate::abtest::ExperimentRunMetadata;
use crate::bluebench::BluebenchResult;
use crate::cache::KvCache;
use crate::chroot::Chroot;
use crate::config::Config;
use crate::cros::ensure_testing_rsa_is_there;
use crate::dut::SshInfo;
use crate::repo::get_cros_dir;
use crate::util::shell_helpers::get_async_lines;
use crate::util::shell_helpers::run_bash_command_async;

#[derive(Debug, Serialize, Deserialize, Clone)]
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

pub fn collect_results(
    cros: Option<&str>,
    results_dir: Option<&str>,
    start: Option<&str>,
    end: Option<&str>,
) -> Result<Vec<TastResultMetadata>> {
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
    info!("{} test invocations found", results.len());
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
                    (None, None) => true,
                }
            } else {
                false
            }
        })
        .cloned()
        .collect();
    info!("{} test invocations in the specified range", results.len());
    let results: Vec<TastResultMetadata> = results
        .iter()
        .flat_map(|p| -> Result<Vec<TastResultMetadata>, ()> {
            let invocation = TastInvocationMetadata::from_path(p).map_err(|e| {
                warn!("{p:?}: {e:?}");
            })?;
            let results_json = results_json_from_path(p).map_err(|e| {
                warn!("{p:?}: {e:?}");
            })?;
            eprint!(".");
            let results: Vec<TastResultMetadata> = results_json
                .1
                .iter()
                .map(|result_json_item| TastResultMetadata {
                    invocation: invocation.clone(),
                    result_json_item: result_json_item.clone(),
                })
                .collect();
            Ok(results)
        })
        .flatten()
        .collect();
    eprintln!();
    info!("{} test invocations are succeeded", results.len());
    Ok(results)
}

/// Subset of /tmp/tast/results/*/results.json
type TastResultJson = Vec<TastResultsJsonItem>;
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct TastResultsJsonError {
    time: String,
    reason: String,
}
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct TastResultsJsonItem {
    pub name: String,
    pub errors: Option<Vec<TastResultsJsonError>>,
}

pub fn results_json_from_path(path: &Path) -> Result<(PathBuf, TastResultJson)> {
    let results_json = path.join("results.json");
    let results_json = std::fs::File::open(results_json)?;
    let results_json = std::io::BufReader::new(results_json);
    let results_json = serde_json::from_reader(results_json)?;
    Ok((path.to_path_buf(), results_json))
}

pub fn test_names_from_path(path: &Path) -> Result<Vec<(PathBuf, String)>> {
    let e = results_json_from_path(path)?;
    let (path, e) = &e;
    Ok(e.iter().map(|e| (path.clone(), e.name.clone())).collect())
}

pub fn experiments_in_results(results: &[PathBuf]) -> Result<HashMap<String, Vec<PathBuf>>> {
    let keys: Vec<String> = results
        .iter()
        .flat_map(|s| -> Option<String> {
            Some(
                s.file_name()?
                    .to_string_lossy()
                    .split('_')
                    .next()
                    .unwrap_or("UNKNOWN")
                    .to_string(),
            )
        })
        .collect();
    let keys: HashSet<String> = HashSet::from_iter(keys.iter().cloned());
    info!("{} experiments found", keys.len());
    info!("{keys:?}");
    Ok(HashMap::new())
}

pub fn tests_in_results(results: &[PathBuf]) -> Result<HashMap<String, Vec<PathBuf>>> {
    let results: Vec<(PathBuf, String)> = results
        .iter()
        .flat_map(|e| test_names_from_path(e))
        .flatten()
        .collect();
    let keys: HashSet<String> = HashSet::from_iter(results.iter().map(|e| e.1.clone()));
    info!("{} tests found", keys.len());
    info!("{keys:?}");
    Ok(HashMap::new())
}

pub fn models_in_results(results: &[PathBuf]) -> Result<HashMap<String, Vec<PathBuf>>> {
    let results: Vec<(PathBuf, String)> = results
        .iter()
        .flat_map(|e| -> Result<(PathBuf, String)> {
            Ok((
                e.clone(),
                TastInvocationMetadata::from_path(e)?
                    .model()
                    .context("No model populated")?
                    .to_string(),
            ))
        })
        .collect();
    let keys: HashSet<String> = HashSet::from_iter(results.iter().map(|e| e.1.clone()));
    info!("{} models found", keys.len());
    info!("{keys:?}");
    Ok(HashMap::new())
}

pub fn os_release_in_results(results: &[PathBuf]) -> Result<HashMap<String, Vec<PathBuf>>> {
    let results: Vec<(PathBuf, String)> = results
        .iter()
        .flat_map(|e| -> Result<(PathBuf, String)> {
            Ok((
                e.clone(),
                TastInvocationMetadata::from_path(e)?
                    .os_release()
                    .to_string(),
            ))
        })
        .collect();
    let keys: HashSet<String> = HashSet::from_iter(results.iter().map(|e| e.1.clone()));
    info!("{} os releases found", keys.len());
    info!("{keys:?}");
    Ok(HashMap::new())
}

pub fn kernel_cmdline_masked_in_results(
    results: &[PathBuf],
) -> Result<HashMap<String, Vec<PathBuf>>> {
    let results: Vec<(PathBuf, String)> = results
        .iter()
        .flat_map(|e| -> Result<(PathBuf, String)> {
            Ok((
                e.clone(),
                TastInvocationMetadata::from_path(e)?
                    .kernel_cmdline_masked()
                    .to_string(),
            ))
        })
        .collect();
    let keys: HashSet<String> = HashSet::from_iter(results.iter().map(|e| e.1.clone()));
    info!("{} kernel cmdline found", keys.len());
    for k in keys {
        info!("{k}");
    }
    Ok(HashMap::new())
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TastResultMetadata {
    pub invocation: TastInvocationMetadata,
    pub result_json_item: TastResultsJsonItem,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TastInvocationMetadata {
    pub path: PathBuf,
    pub os_release: String,
    pub model: Option<String>,
    pub kernel_cmdline: String,
    pub kernel_cmdline_masked: String,
    pub abtest_metadata: Option<ExperimentRunMetadata>,
    pub bluebench_result: Option<BluebenchResult>,
}
impl TastInvocationMetadata {
    fn probe_os_release(path: &Path) -> Result<String> {
        let path = path.join("system_logs").join("lsb-release");
        let s = std::fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let s: Vec<&str> = s.split('\n').collect();
        let s: Vec<&&str> = s
            .iter()
            .filter(|s| s.contains("CHROMEOS_RELEASE_BUILDER_PATH="))
            .collect();
        let s = s.last().context("no text found")?;
        let s = s.split('=').nth(1).context("invalid release version")?;
        let s = s.trim();
        Ok(s.to_string())
    }
    fn probe_model(path: &Path) -> Result<String> {
        let path = path.join("dut-info.txt");
        let s = std::fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let s: Vec<&str> = s.split('\n').collect();
        if let Some(s) = s
            .iter()
            .skip_while(|s| !s.contains("deprecated_device_config"))
            .find(|s| s.contains("model:"))
        {
            Ok(s.split(':')
                .last()
                .context("model format error")?
                .trim()
                .trim_matches('"')
                .to_string())
        } else {
            Err(anyhow!("model info not found in dut-info.txt"))
        }
    }
    fn probe_kernel_cmdline(path: &Path) -> Result<String> {
        let path = path.join("system_logs").join("dmesg.txt");
        let s = std::fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let s = s
            .split('\n')
            .find(|s| s.contains("Kernel command line:"))
            .context(anyhow!("Kernel command line not found in the dmesg.txt"))?;
        let s = &s[s.find(':').map(|i| i + 1).unwrap_or_default()..].trim();
        Ok(s.to_string())
    }
    fn to_kernel_cmdline_masked(s: &str) -> Result<String> {
        static RE_CMDLINE_DM_HASH: Lazy<Regex> = Lazy::new(|| Regex::new("[0-9a-z]{64}").unwrap());
        static RE_CMDLINE_UUID: Lazy<Regex> = Lazy::new(|| {
            Regex::new("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}").unwrap()
        });
        static RE_CMDLINE_CROS_LSB_RELEASE_HASH: Lazy<Regex> =
            Lazy::new(|| Regex::new("cros_lsb_release_hash=.{44}").unwrap());
        let s = RE_CMDLINE_DM_HASH.replace_all(s, "{HASH{64}}");
        let s = RE_CMDLINE_UUID.replace_all(&s, "{UUID}");
        let s = RE_CMDLINE_CROS_LSB_RELEASE_HASH.replace_all(&s, "{CROS_LSB_HASH}");
        Ok(s.to_string())
    }
    fn probe_abtest_metadata(path: &Path) -> Result<ExperimentRunMetadata> {
        let path = path.join("cro3_abtest_run_metadata.json");
        let s = std::fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let d = serde_json::from_str(&s).context("Failed to parse");
        if let Err(e) = &d {
            warn!("{path:?}: Failed to parse cro3 abtest metadata: {e}");
        }
        d
    }
    pub fn model(&self) -> Option<&str> {
        self.model.as_deref()
    }
    pub fn os_release(&self) -> &str {
        &self.os_release
    }
    pub fn kernel_cmdline(&self) -> &str {
        &self.kernel_cmdline
    }
    pub fn kernel_cmdline_masked(&self) -> &str {
        &self.kernel_cmdline_masked
    }
    pub fn abtest_metadata(&self) -> Option<&ExperimentRunMetadata> {
        self.abtest_metadata.as_ref()
    }
    pub fn from_path(path: &Path) -> Result<Self> {
        let path = path.to_path_buf();
        let os_release = Self::probe_os_release(&path)?;
        let model = Self::probe_model(&path).ok();
        let kernel_cmdline = Self::probe_kernel_cmdline(&path)?;
        let kernel_cmdline_masked = Self::to_kernel_cmdline_masked(&kernel_cmdline)?;
        let abtest_metadata = Self::probe_abtest_metadata(&path).ok();
        let bluebench_result = BluebenchResult::from_path(&path).ok();
        Ok(Self {
            path,
            os_release,
            model,
            kernel_cmdline,
            kernel_cmdline_masked,
            abtest_metadata,
            bluebench_result,
        })
    }
}

pub fn save_result_metadata_json(
    results: &[&TastResultMetadata],
    prefix: Option<&str>,
) -> Result<()> {
    let path = if let Some(prefix) = prefix {
        format!("{prefix}_parsed_results.json")
    } else {
        "parsed_results.json".to_string()
    };
    let path = Path::new("out").join(path);
    let mut f = std::fs::File::create(&path)?;
    f.write_all(&serde_json::to_string(&results)?.into_bytes())?;
    info!("Generated {path:?}");
    Ok(())
}

#[derive(Serialize, Deserialize, Debug, Default)]
struct TastAnalyzerScalarResult {
    units: String,
    improvement_direction: String,
    value: f64,
}

#[derive(Serialize, Deserialize, Debug, Default)]
pub struct TastAnalyzerResultJsonKey {
    run_id: String,
    test_name: String,
    metric_name: String,
    variant: String,
}

#[derive(Serialize, Deserialize, Debug, Default)]
pub struct TastAnalyzerInputJson(HashMap<String, String>);

impl TastAnalyzerInputJson {
    pub fn save(&self, path: &Path) -> Result<()> {
        let mut f = File::create(path)?;
        f.write_all(&serde_json::to_string(&self)?.into_bytes())?;
        info!("Generated {path:?}");
        Ok(())
    }
    pub fn from_results(results: &[&TastResultMetadata]) -> Result<Self> {
        let mut data = Self::default();
        for r in results {
            let abtest_metadata = r
                .invocation
                .abtest_metadata
                .as_ref()
                .context("abtest_metadata should be populated")?;
            let tast_test = &abtest_metadata.runner.tast_test;
            let r = r
                .invocation
                .bluebench_result
                .as_ref()
                .context("bluebench_result is empty")?;
            let value = r.converged_mean_mean;
            let v = TastAnalyzerScalarResult {
                units: "milliseconds".to_string(),
                improvement_direction: "down".to_string(),
                value,
            };
            let ts = chrono::DateTime::parse_from_rfc3339(
                r.metadata
                    .test_start_timestamp
                    .split(' ')
                    .next()
                    .context("failed to get test start timestamp")?,
            )
            .context("failed to parse test start timestamp")?;
            let hwid = &r.metadata.hwid;
            let k = TastAnalyzerResultJsonKey {
                run_id: format!("{hwid}/{ts}"),
                test_name: tast_test.clone(),
                metric_name: "TabOpenLatency".to_string(),
                variant: String::default(),
            };
            let k = serde_json::to_string(&k)?;
            let v = serde_json::to_string(&v)?;
            data.0.insert(k, v);
        }
        Ok(data)
    }
}
