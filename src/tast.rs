// Copyright 2023 The ChEomiumOS Authors
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
use std::fs::read_to_string;
use std::fs::File;
use std::io::Write;
use std::path::Path;
use std::path::PathBuf;
use std::fmt::Display;

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
use rayon::prelude::*;
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
        .par_iter()
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
        .par_iter()
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
                .flat_map(|result_json_item| -> Result<TastResultMetadata> {
                    let test_name = &result_json_item.name;
                    let results_chart_json = invocation
                        .path
                        .join("tests")
                        .join(test_name)
                        .join("results-chart.json");
                    let results_chart_json = if results_chart_json.exists() {
                        let results_chart_json = read_to_string(&results_chart_json)?;
                        let results_chart_json: TastResultsChartJson =
                            serde_json::from_str(&results_chart_json)?;
                        Some(results_chart_json)
                    } else {
                        None
                    };

                    Ok(TastResultMetadata {
                        invocation: invocation.clone(),
                        result_json_item: result_json_item.clone(),
                        results_chart_json,
                    })
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
    pub results_chart_json: Option<TastResultsChartJson>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TastResultsChartJsonItem {
    units: String,
    improvement_direction: String,
    value: Option<f64>,
    values: Option<Vec<f64>>,
}
pub type TastResultsChartJson = HashMap<String, HashMap<String, TastResultsChartJsonItem>>;

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
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut f = std::fs::File::create(path)?;
    f.write_all(&serde_json::to_string(&results)?.into_bytes())?;
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

#[derive(Debug, PartialEq, Clone, Serialize)]
pub struct TastAnalyzerOutputAnalysisLine {
    pub u: f64,
    pub p: f64,
    pub dir: String,
    pub cnt_a: usize,
    pub cnt_b: usize,
    pub change_percent: f64,
}
impl TastAnalyzerOutputAnalysisLine {
    pub fn from(stats: &str) -> Result<Self> {
        static RE_ANALYSIS: Lazy<Regex> = Lazy::new(|| {
            Regex::new(r"U=(?<u>[0-9.]+), p=(?<p>.*), dir=(?<dir>.*), n=\((?<cnt_a>.*), (?<cnt_b>.*)\), %change=(?<change_percent>[0-9-.]+)").unwrap()
        });
        let stats = RE_ANALYSIS.captures(stats).context("No stat line match")?;
        let u = stats.name("u").context("u is missing")?.as_str();
        let u = u.parse().context("failed to parse U")?;
        let p = stats.name("p").context("p is missing")?.as_str();
        let p = p.parse().context("failed to parse U")?;
        let dir = stats
            .name("dir")
            .context("dir is missing")?
            .as_str()
            .to_string();
        let cnt_a = stats.name("cnt_a").context("cnt_a is missing")?.as_str();
        let cnt_a = cnt_a.parse().context("failed to parse U")?;
        let cnt_b = stats.name("cnt_b").context("cnt_b is missing")?.as_str();
        let cnt_b = cnt_b.parse()?;
        let change_percent = stats
            .name("change_percent")
            .context("change_percent is missing")?
            .as_str();
        let change_percent = change_percent.parse()?;
        Ok(Self {
            u,
            p,
            dir,
            cnt_a,
            cnt_b,
            change_percent,
        })
    }
}

#[derive(Debug, PartialEq, Clone, Serialize)]
pub struct TastAnalyzerOutputStatsLine {
    pub mean: f64,
    pub unit: String,
    pub stddev: f64,
    pub min: f64,
    pub max: f64,
}
impl TastAnalyzerOutputStatsLine {
    pub fn from(stats: &str) -> Result<Self> {
        static RE_STATS: Lazy<Regex> = Lazy::new(|| {
            // mean=108.65 milliseconds, std=3.33, min=98.31, max=113.07
            Regex::new(r"mean=(?<mean>[0-9.]+) (?<unit>[^,]+), std=(?<stddev>[0-9.]+), min=(?<min>[0-9.]+), max=(?<max>.*)").unwrap()
        });
        let stats = RE_STATS.captures(stats).context("No stat line match")?;
        let mean = stats.name("mean").context("mean is missing")?.as_str();
        let mean = mean.parse().context("failed to parse mean")?;
        let unit = stats
            .name("unit")
            .context("unit is missing")?
            .as_str()
            .to_string();
        let stddev = stats.name("stddev").context("stddev is missing")?.as_str();
        let stddev = stddev.parse().context("failed to parse mean")?;
        let min = stats.name("min").context("min is missing")?.as_str();
        let min = min.parse().context("failed to parse mean")?;
        let max = stats.name("max").context("max is missing")?.as_str();
        let max = max.parse().context("failed to parse mean")?;
        Ok(Self {
            mean,
            unit,
            stddev,
            min,
            max,
        })
    }
}

#[derive(Debug, PartialEq, Clone, Serialize)]
pub struct TastAnalyzerOutput {
    pub key: String,
    pub analysis: TastAnalyzerOutputAnalysisLine,
    pub stats_a: TastAnalyzerOutputStatsLine,
    pub stats_b: TastAnalyzerOutputStatsLine,
}
impl TastAnalyzerOutput {
    pub fn from(output: &str) -> Result<Vec<Self>> {
        let mut results = Vec::new();
        let output: Vec<&str> = output
            .split('\n')
            .filter(|s| s.starts_with("  ") | s.ends_with(':'))
            .map(|s| s.trim())
            .collect();
        for e in output.chunks(4) {
            if let (Some(key), Some(analysis), Some(a), Some(b)) =
                (e.first(), e.get(1), e.get(2), e.get(3))
            {
                let key = key.to_string();
                let analysis = TastAnalyzerOutputAnalysisLine::from(analysis)?;
                let stats_a = TastAnalyzerOutputStatsLine::from(a)?;
                let stats_b = TastAnalyzerOutputStatsLine::from(b)?;
                results.push(TastAnalyzerOutput {
                    key,
                    analysis,
                    stats_a,
                    stats_b,
                })
            }
        }
        Ok(results)
    }
}
impl Display for TastAnalyzerOutput {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "  {:>+6.2}% change with p={:.6} on {}:\n  {:12.3} => {:12.3} [{}], N=({:3}, {:3})", 
            self.analysis.change_percent,
            self.analysis.p, 
            self.key, 
            self.stats_a.mean, 
            self.stats_b.mean,
            self.stats_a.unit, 
            self.analysis.cnt_a, 
            self.analysis.cnt_b)
    }
}

#[test]
fn tast_analyzer_one_output_can_be_parsed() {
    let stdout = r#"
1 metrics, 1 better, 0 worse
0 GOT WORSE FROM A.json to B.json

1 GOT BETTER FROM A.json to B.json
perf.TabOpenLatencyPerf.TabOpenLatency.:
  U=3540.0, p=0.000000, dir=down, n=(59, 60), %change=-17.94
  mean=108.65 milliseconds, std=3.33, min=98.31, max=113.07
  mean=89.16 milliseconds, std=2.48, min=82.91, max=93.48
"#;
    let actual = TastAnalyzerOutput::from(stdout).unwrap();
    assert_eq!(actual.len(), 1);
    let actual = actual[0].clone();
    let expected = TastAnalyzerOutput {
        key: "perf.TabOpenLatencyPerf.TabOpenLatency.:".to_string(),
        analysis: TastAnalyzerOutputAnalysisLine {
            u: 3540.0,
            p: 0.0,
            dir: "down".to_string(),
            cnt_a: 59,
            cnt_b: 60,
            change_percent: -17.94,
        },
        stats_a: TastAnalyzerOutputStatsLine {
            mean: 108.65,
            unit: "milliseconds".to_string(),
            stddev: 3.33,
            min: 98.31,
            max: 113.07,
        },
        stats_b: TastAnalyzerOutputStatsLine {
            mean: 89.16,
            unit: "milliseconds".to_string(),
            stddev: 2.48,
            min: 82.91,
            max: 93.48,
        },
    };
    println!("{actual}");
    assert_eq!(actual, expected);
}

#[test]
fn tast_analyzer_zero_output_can_be_parsed() {
    let stdout = r#"
0 metrics, 0 better, 0 worse
0 GOT WORSE FROM experiment_20240619_164907_892671708_kled_A.json to experiment_20240619_164907_892671708_kled_B.json

0 GOT BETTER FROM experiment_20240619_164907_892671708_kled_A.json to experiment_20240619_164907_892671708_kled_B.json
"#;
    let actual = TastAnalyzerOutput::from(stdout).unwrap();
    assert_eq!(actual.len(), 0);
}
