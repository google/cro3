// Copyright 2024 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

//! ## Run / analyze performance experiments
//! ```
//! START_DATE?=$(shell date -d '2 hours ago' +%Y%m%d-%H%M%S)
//! END_DATE?=$(shell date -d 'now' +%Y%m%d-%H%M%S)
//! # START_DATE?=20240507-000000
//! cro3 abtest analyze --serve --cros /work/chromiumos/ --start $(START_DATE) --end $(END_DATE) --test-name perf.TabOpenLatencyPerf --port 8080
//! cro3 abtest analyze --generate --cros /work/chromiumos/ --start $(START_DATE) --end $(END_DATE) --test-name perf.TabOpenLatencyPerf
//! ```
//! If you want to re-build and serve automatically, you can use:
//! ```
//! cargo install cargo-watch
//! cargo watch -x run -- abtest analyze --serve --cros /work/chromiumos/ --start $(START_DATE) --end $(END_DATE) --test-name perf.TabOpenLatencyPerf --port 8080
//! ```

use std::collections::BTreeSet;
use std::collections::HashMap;
use std::collections::HashSet;
use std::ffi::OsStr;
use std::fs;
use std::fs::read_dir;
use std::io::BufWriter;
use std::io::Read;
use std::io::Write;
use std::net::TcpListener;
use std::net::TcpStream;
use std::path::Path;
use std::path::PathBuf;
use std::thread::spawn;

use anyhow::anyhow;
use anyhow::bail;
use anyhow::Context;
use anyhow::Result;
use argh::FromArgs;
use cro3::chroot::Chroot;
use cro3::dut::SshInfo;
use cro3::repo::get_cros_dir;
use lazy_static::lazy_static;
use rayon::prelude::*;
use regex::Regex;
use serde::Deserialize;
use serde::Serialize;
use tracing::error;
use tracing::info;
use tracing::warn;

use crate::cmd::tast::run_tast_test;

#[derive(FromArgs, PartialEq, Debug)]
/// Run / analyze performance experiments
#[argh(subcommand, name = "abtest")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}
impl Args {
    #[tracing::instrument(level = "trace")]
    pub fn run(&self) -> Result<()> {
        match &self.nested {
            SubCommand::Run(args) => args.run(),
            SubCommand::Analyze(args) => args.run(),
        }
    }
}
#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    Run(ArgsRun),
    Analyze(ArgsAnalyze),
}

#[derive(Debug)]
enum ExperimentConfig {
    A,
    B,
}

#[derive(FromArgs, PartialEq, Debug)]
/// Run performance experiments
#[argh(subcommand, name = "run")]
struct ArgsRun {
    /// cros repo dir to be used
    #[argh(option)]
    cros: String,

    /// target DUT
    #[argh(option)]
    dut: String,

    /// path to a device initialization script
    #[argh(option)]
    script_init: Option<String>,

    /// path to a setup script for experiment config A
    #[argh(option)]
    script_config_a: String,

    /// path to a setup script for experiment config B
    #[argh(option)]
    script_config_b: String,

    /// tast test identifier
    #[argh(option)]
    tast_test: String,

    /// a group contains one invocation of script_config_a (or b) and some
    /// invocation of tast_test (for run_per_cluster times)
    #[argh(option)]
    run_per_group: Option<usize>,

    /// a cluster contains some groups for config A and config B (for
    /// group_per_cluster times for each config)
    #[argh(option)]
    group_per_cluster: Option<usize>,

    /// an iteration contains one invocation of script_init and some clusters
    /// (cluster_per_iteration times)
    #[argh(option)]
    cluster_per_iteration: Option<usize>,

    /// an experiment contains some iterations (num_of_iterations times)
    #[argh(option)]
    num_of_iterations: Option<usize>,

    /// name of this experiment for identification
    #[argh(option)]
    experiment_name: String,

    /// path to a dir to store the results
    #[argh(option)]
    result_dir: Option<String>,
}
impl ArgsRun {
    fn run_group(&self, config: ExperimentConfig, dut: &SshInfo) -> Result<()> {
        let repodir = get_cros_dir(Some(&self.cros))?;
        let chroot = Chroot::new(&repodir)?;
        match config {
            ExperimentConfig::A => dut.switch_partition_set(cro3::dut::PartitionSet::Primary),
            ExperimentConfig::B => dut.switch_partition_set(cro3::dut::PartitionSet::Secondary),
        }?;
        if let Err(e) = dut.reboot() {
            warn!("reboot failed (ignored): {e:?}");
        }
        dut.wait_online()?;

        for i in 0..self.run_per_group.unwrap_or(20) {
            info!("#### run {i}");
            retry::retry(retry::delay::Fixed::from_millis(500).take(3), || {
                run_tast_test(&chroot, dut, &self.tast_test, None)
            })
            .or(Err(anyhow!("Failed to run tast test after retries")))?;
        }
        Ok(())
    }
    fn run_cluster(&self, dut: &SshInfo) -> Result<()> {
        for i in 0..self.group_per_cluster.unwrap_or(1) {
            info!("### group A-{i}");
            self.run_group(ExperimentConfig::A, dut)?;
        }
        for i in 0..self.group_per_cluster.unwrap_or(1) {
            info!("### group A-{i}");
            self.run_group(ExperimentConfig::B, dut)?;
        }
        Ok(())
    }
    fn run_iteration(&self, dut: &SshInfo) -> Result<()> {
        for i in 0..self.cluster_per_iteration.unwrap_or(1000) {
            info!("## cluster {i}");
            self.run_cluster(dut)?;
        }
        Ok(())
    }
    fn run_experiment(&self, dut: &SshInfo) -> Result<()> {
        for i in 0..self.num_of_iterations.unwrap_or(1) {
            info!("# iteration {i}");
            self.run_iteration(dut)?;
        }
        Ok(())
    }
    fn run(&self) -> Result<()> {
        let dut = SshInfo::new(&self.dut)?;
        let dut = dut.into_forwarded()?;
        self.run_experiment(dut.ssh())
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// Analyze performance experiment result
#[argh(subcommand, name = "analyze")]
struct ArgsAnalyze {
    /// serve the result
    #[argh(switch)]
    generate: bool,

    /// cros source dir to be used for data retrieval(exclusive with
    /// --results-dir)
    #[argh(option)]
    cros: Option<String>,
    /// results dir to be used (exclusive with --cros)
    #[argh(option)]
    results_dir: Option<String>,
    /// start datetime to be analyzed in YYYYMMDD-hhmmss format.
    #[argh(option)]
    start: Option<String>,
    /// end datetime to be analyzed in YYYYMMDD-hhmmss format.
    #[argh(option)]
    end: Option<String>,
    /// only process one succesfull result and dump the result (for testing)
    #[argh(switch)]
    test: bool,
    /// test name (e.g. perf.TabOpenLatency)
    #[argh(option)]
    test_name: Option<String>,
    /// hwid
    #[argh(option)]
    hwid: Option<String>,

    /// serve the result
    #[argh(switch)]
    serve: bool,
    /// port
    #[argh(option, default = "8080")]
    port: u16,

    /// list DUT information from the specified results
    #[argh(switch)]
    list_duts: bool,
}
impl ArgsAnalyze {
    fn run(&self) -> Result<()> {
        info!("{self:?}");
        if self.generate {
            let test_name = self
                .test_name
                .as_ref()
                .context("--test-name should be specified")?;
            generate(self, test_name)?;
        }
        if self.serve {
            listen_http(self.port)?;
        }
        if self.list_duts {
            let test_name = self
                .test_name
                .as_ref()
                .context("--test-name should be specified")?;
            let hwid_and_info_map = hwid_and_info_map(self, test_name)?;
            for (hwid, info_set) in hwid_and_info_map {
                println!("{hwid}");
                for info in info_set {
                    println!("  {}", info.serial_number);
                    println!("    {}", info.cpu_product_name);
                    println!("    {}", info.cpu_bugs);
                }
            }
        }
        Ok(())
    }
}

const HTTP_RESPONSE_HEADER_200_OK: &str = r#"HTTP/1.1 200 OK"#;
const HTTP_RESPONSE_HEADER_404_NOT_FOUND: &str = r#"HTTP/1.1 404 NOT FOUND"#;
const HTTP_RESPONSE_HEADER_KEEP_ALIVE: &str = r#"Keep-Alive: timeout=5, max=100"#;
const HTTP_RESPONSE_HEADER_HTML_UTF8: &str = r#"Content-Type: text/html; charset=UTF-8"#;
const HTTP_RESPONSE_HEADER_JSON_UTF8: &str = r#"Content-Type: text/json; charset=UTF-8"#;
const HTTP_RESPONSE_HEADER_CSV_UTF8: &str = r#"Content-Type: application/octet-stream"#;
const HTTP_RESPONSE_HEADER_CSS_UTF8: &str = r#"Content-Type: text/css; charset=UTF-8"#;
const HTTP_RESPONSE_HEADER_JS_UTF8: &str = r#"Content-Type: text/javascript; charset=UTF-8"#;

#[derive(Debug, Serialize, Deserialize)]
struct BluebenchCycleResult {
    date: String,
    iter_index: usize,
    status: String,
    converged_mean: Option<f64>,
    t1: Option<f64>,
    t2: Option<f64>,
    t3: Option<f64>,
    raw: Vec<f64>,
}

lazy_static! {
    static ref RE_CSV_PATH: Regex = Regex::new(r"^/[A-Za-z0-9_.]+.csv$").unwrap();
}

#[derive(Debug, Serialize, Deserialize)]
struct BluebenchMetadata {
    path: String,
    key: String,
    dut_id: String,
    hwid: String,
    kernel_version: String,
    os_release: String,
    bootid: String,
    kernel_cmdline_mitigations: String,
    temperature_sensor_readouts: HashMap<String, Vec<(String, f64)>>,
    test_start_timestamp: String,
    test_end_timestamp: String,
}
impl BluebenchMetadata {
    fn cpu_product_name(path: &Path, test_name: &str) -> Result<String> {
        let path = path.join("tests").join(test_name).join("cpuinfo.txt");
        let text = fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let lines: Vec<&str> = text.split('\n').collect();
        let lines: Vec<&&str> = lines
            .iter()
            .filter(|s| s.starts_with("model name"))
            .collect();
        let line = lines.last().context("no text found")?;
        let line = line.split(':').nth(1).context("invalid cpu model name")?;
        let line = line.trim();
        Ok(line.to_string())
    }
    fn cpu_bugs(path: &Path, test_name: &str) -> Result<String> {
        let path = path.join("tests").join(test_name).join("cpuinfo.txt");
        let text = fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let lines: Vec<&str> = text.split('\n').collect();
        let lines: Vec<&&str> = lines.iter().filter(|s| s.starts_with("bugs")).collect();
        let line = lines.last().context("no text found")?;
        let line = line.split(':').nth(1).context("invalid cpu model name")?;
        let line = line.trim();
        Ok(line.to_string())
    }
    fn serial_number(path: &Path, test_name: &str) -> Result<String> {
        let path = path.join("tests").join(test_name).join("vpd.txt");
        let text = fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let lines: Vec<&str> = text.split('\n').collect();
        let lines: Vec<&&str> = lines
            .iter()
            .filter(|s| s.contains("\"serial_number\""))
            .collect();
        let line = lines.last().context("no text found")?;
        let line = line.split('=').nth(1).context("invalid dut_id")?;
        let line = line.split('"').nth(1).context("invalid dut_id")?;
        let line = line.trim();
        Ok(line.to_string())
    }
    fn hwid(path: &Path, test_name: &str) -> Result<String> {
        let path = path.join("tests").join(test_name).join("crossystem.txt");
        let text = fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let lines: Vec<&str> = text.split('\n').collect();
        let lines: Vec<&&str> = lines.iter().filter(|s| s.contains("hwid")).collect();
        let line = lines.last().context("no text found")?;
        let line = line.split('=').nth(1).context("invalid dut_id")?;
        let line = line.split('#').nth(0).context("invalid dut_id")?;
        let line = line.trim();
        Ok(line.to_string())
    }
    fn kernel_version(path: &Path, test_name: &str) -> Result<String> {
        let path = path
            .join("tests")
            .join(test_name)
            .join("kernel_version.txt");
        let s = fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let s = s.split(' ').nth(2).context("invalid dut_id")?;
        let s = s.trim();
        Ok(s.to_string())
    }
    fn os_release(path: &Path, test_name: &str) -> Result<String> {
        let path = path.join("tests").join(test_name).join("lsb_release.txt");
        let s = fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let s: Vec<&str> = s.split('\n').collect();
        let s: Vec<&&str> = s
            .iter()
            .filter(|s| s.contains("CHROMEOS_RELEASE_BUILDER_PATH="))
            .collect();
        let s = s.last().context("no text found")?;
        let s = s.split('=').nth(1).context("invalid dut_id")?;
        let s = s.trim();
        Ok(s.to_string())
    }
    fn bootid(path: &Path, test_name: &str) -> Result<String> {
        let path = path.join("tests").join(test_name).join("bootid.txt");
        let s = fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let s = s.trim();
        Ok(s.to_string())
    }
    fn kernel_cmdline_mitigations(path: &Path, test_name: &str) -> Result<String> {
        let path = path.join("tests").join(test_name).join("cmdline.txt");
        let s = fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let s = s
            .split(' ')
            .find(|s| s.contains("mitigations="))
            .unwrap_or("")
            .trim();
        Ok(s.to_string())
    }
    fn parse_temp_log_line(s: &str) -> Result<(String, HashMap<String, f64>)> {
        let mut data: HashMap<String, f64> = HashMap::new();
        let mut it = s.trim().split(' ');
        let t = it.next().context("timestamp should be there")?.to_string();
        let it = it.skip_while(|s| !s.starts_with("x86_pkg_temp"));
        for e in it {
            let mut it = e.split(':');
            let mut key = it.next().context("name should be there")?.to_string();
            let value: &str = it.next().context("value should be there")?;
            let unit = value.chars().last().context("unit should be there")?; // Assuming that the last char is unit (e.g. C, W)
            let value = &value[..value.len() - 1];
            let value: f64 = value.parse().context("failed to parse temp value")?;
            key.push('_');
            key.push(unit);
            data.insert(key, value);
        }
        Ok((t, data))
    }
    fn temperature_sensor_readouts(
        path: &Path,
        test_name: &str,
        test_start_timestamp: &str,
        test_end_timestamp: &str,
    ) -> Result<HashMap<String, Vec<(String, f64)>>> {
        let mut temp_data: HashMap<String, Vec<(String, f64)>> = HashMap::new();
        let path = path.join("tests").join(test_name).join("messages.txt");
        let s = fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let s: Vec<(String, HashMap<String, f64>)> = s
            .split('\n')
            .filter(|s| s.contains("x86_pkg_temp"))
            .filter_map(|s| Self::parse_temp_log_line(s).ok())
            .collect();
        for (t, entries) in s {
            if t.as_str() < test_start_timestamp || test_end_timestamp < t.as_str() {
                continue;
            }
            for (k, v) in entries {
                if !temp_data.contains_key(&k) {
                    temp_data.insert(k.clone(), Vec::new());
                }
                temp_data
                    .get_mut(&k)
                    .context("key should have value")?
                    .push((t.to_string(), v));
            }
        }
        Ok(temp_data)
    }
    fn test_start_end_timestamp(path: &Path, test_name: &str) -> Result<(String, String)> {
        let path = path.join("tests").join(test_name).join("log.txt");
        let s = fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let mut it = s.split('\n');
        let start_ts = it
            .find(|s| s.contains("Started test"))
            .context("Started test line not found");
        let end_ts = it
            .find(|s| s.contains("Completed test"))
            .context("Started test line not found");
        Ok((start_ts?.to_string(), end_ts?.to_string()))
    }
    fn from_path(path: &Path, test_name: &str) -> Result<Self> {
        let dut_id = Self::serial_number(path, test_name)
            .or_else(|_| Result::<String>::Ok("NoSerial".to_string()))?;
        let hwid = Self::hwid(path, test_name)?;
        let (test_start_timestamp, test_end_timestamp) =
            Self::test_start_end_timestamp(path, test_name)?;
        let kernel_version = Self::kernel_version(path, test_name)?;
        let os_release = Self::os_release(path, test_name)?;
        let bootid = Self::bootid(path, test_name)?;
        let kernel_cmdline_mitigations = Self::kernel_cmdline_mitigations(path, test_name)?;
        let temperature_sensor_readouts = Self::temperature_sensor_readouts(
            path,
            test_name,
            &test_start_timestamp,
            &test_end_timestamp,
        )?;
        let key = format!("{hwid}/{dut_id}/{bootid}/{kernel_cmdline_mitigations}");
        let path = path.as_os_str().to_string_lossy().into_owned().to_string();
        Ok(Self {
            path,
            key,
            dut_id,
            hwid,
            kernel_version,
            os_release,
            bootid,
            kernel_cmdline_mitigations,
            temperature_sensor_readouts,
            test_start_timestamp,
            test_end_timestamp,
        })
    }
}

#[test]
fn parse_x86_temp_info() {
    let data = BluebenchMetadata::parse_temp_log_line(
        "2024-05-09T06:36:29.997016Z NOTICE temp_logger[10343]:  x86_pkg_temp:47C \
         INT3400_Thermal:20C TSR0:48C TSR1:0C TSR2:46C TSR3:43C TSR4:37C TCPU:52C TCPU_PCI:54C \
         PL1:15.000W",
    )
    .unwrap();
    assert_eq!(data.0, "2024-05-09T06:36:29.997016Z");
    assert_eq!(data.1.len(), 10);
    assert_eq!(data.1["x86_pkg_temp_C"], 47.0f64);
    assert_eq!(data.1["INT3400_Thermal_C"], 20.0f64);
    assert_eq!(data.1["TSR0_C"], 48.0f64);
    assert_eq!(data.1["TSR1_C"], 0.0f64);
    assert_eq!(data.1["TSR2_C"], 46.0f64);
    assert_eq!(data.1["TSR3_C"], 43.0f64);
    assert_eq!(data.1["TSR4_C"], 37.0f64);
    assert_eq!(data.1["TCPU_C"], 52.0f64);
    assert_eq!(data.1["TCPU_PCI_C"], 54.0f64);
    assert_eq!(data.1["PL1_W"], 15.0f64);
}

#[derive(Debug, Serialize, Deserialize)]
struct BluebenchResult {
    metadata: BluebenchMetadata,
    last_result_date: String,
    converged_mean_mean: f64,
    cycles: Vec<BluebenchCycleResult>,
}

fn analyze_one_result(
    path: &PathBuf,
    test_name: &str,
    hwid_expected: Option<&str>,
) -> Result<BluebenchResult> {
    let t0 = std::time::Instant::now();
    if let Some(hwid_expected) = hwid_expected {
        let hwid = BluebenchMetadata::hwid(path, test_name)?;
        if hwid != hwid_expected {
            // Only parse results from some hwid to speed up the parsing
            bail!("Skipping due to hwid mismatch");
        }
    }
    let metadata = BluebenchMetadata::from_path(path, test_name)?;
    let result_csv = path.join("tests").join(test_name).join("bluebench_log.txt");
    if !result_csv.is_file() {
        bail!("{result_csv:?} is not a file");
    }
    let result_text = fs::read_to_string(&result_csv)
        .context(anyhow!("Failed to read the result file: {:?}", &result_csv))?;
    let result_lines: Vec<&str> = result_text.split('\n').collect();
    let parse_f64_optional = |s: Option<&&str>| -> Result<Option<f64>> {
        if let Some(v) = s {
            if v.is_empty() {
                Ok(None)
            } else {
                Ok(Some(
                    v.parse()
                        .context(anyhow!("converged_mean ({v}) is invalid"))?,
                ))
            }
        } else {
            Ok(None)
        }
    };
    let cycles: Vec<BluebenchCycleResult> = result_lines
        .iter()
        .map(|s| -> &str { str::trim(s) })
        .filter(|s| !s.is_empty())
        .map(|line| -> Result<BluebenchCycleResult> {
            let line: Vec<&str> = line.split(',').collect();
            let date = line.first().context("Date is invalid")?.to_string();
            let iter_index: usize = line
                .get(1)
                .context("Iter index was empty")?
                .parse()
                .context("Failed to parse iter index")?;
            let status = line.get(2).unwrap_or(&"Invalid").to_string();
            let converged_mean = parse_f64_optional(line.get(3))?;
            let t1 = parse_f64_optional(line.get(4))?;
            let t2 = parse_f64_optional(line.get(5))?;
            let t3 = parse_f64_optional(line.get(6))?;
            let raw: Vec<f64> = line[7..]
                .iter()
                .map(|e| -> f64 { e.parse().unwrap() })
                .collect();
            Ok(BluebenchCycleResult {
                date,
                iter_index,
                status,
                converged_mean,
                t1,
                t2,
                t3,
                raw,
            })
        })
        .collect::<Result<Vec<BluebenchCycleResult>>>()?;
    let converged_means: Vec<f64> = cycles.iter().filter_map(|c| c.converged_mean).collect();
    let converged_mean_mean = converged_means.iter().sum::<f64>() / converged_means.len() as f64;
    let last_result_date = cycles.last().unwrap().date.clone();
    info!("parse done: {:?} {:?}", t0.elapsed(), path);
    Ok(BluebenchResult {
        metadata,
        last_result_date,
        cycles,
        converged_mean_mean,
    })
}

fn analyze_all(results: Vec<PathBuf>, test_name: &str, hwid: Option<&str>) -> Vec<BluebenchResult> {
    results
        .par_iter()
        .flat_map(|e| analyze_one_result(e, test_name, hwid))
        .collect()
}

fn analyze_latest_succesfull(results: Vec<PathBuf>, test_name: &str) -> Vec<BluebenchResult> {
    results
        .iter()
        .rev()
        .flat_map(|e| analyze_one_result(e, test_name, None))
        .take(5)
        .collect()
}

fn write_latency_csv(
    results: &[BluebenchResult],
    result_key_order: &HashMap<String, usize>,
) -> Result<()> {
    // Generate
    let mut data: Vec<(String, f64, String)> = results
        .iter()
        .map(|r| {
            (
                r.last_result_date.to_string(),
                r.converged_mean_mean,
                r.metadata.key.to_string(),
            )
        })
        .collect();
    data.sort_by(|l, r| l.0.cmp(&r.0));
    data.dedup();
    // Write
    let mut csv_file = fs::File::create("data.csv")?;
    // header
    let mut header_keys: Vec<(&String, &usize)> =
        result_key_order.iter().collect::<Vec<(&String, &usize)>>();
    header_keys.sort_by_key(|e| e.1);
    let header_keys: Vec<String> = header_keys.iter().map(|e| e.0.clone()).collect();
    writeln!(csv_file, "t,{}", header_keys.join(","))?;
    // data
    for e in data.iter() {
        let key_order: usize = result_key_order[&e.2];
        writeln!(
            csv_file,
            "{},{}{}{}",
            e.0,
            ",".repeat(key_order),
            e.1,
            ",".repeat(result_key_order.len() - 1 - key_order),
        )?;
    }
    info!("Generated data.csv");
    Ok(())
}

fn write_temp_csv(
    results: &[BluebenchResult],
    result_key_order: &HashMap<String, usize>,
    temp_key: &str,
    file_name: &str,
) -> Result<()> {
    // Generate
    let mut data: Vec<(String, f64, String)> = results
        .iter()
        .flat_map(|r| {
            let k = &r.metadata.key;
            r.metadata
                .temperature_sensor_readouts
                .get(temp_key)
                .map(|e| {
                    e.iter()
                        .map(|(t, v)| (t.clone(), *v, k.clone()))
                        .collect::<Vec<(String, f64, String)>>()
                })
                .unwrap_or_default()
        })
        .collect();
    data.sort_by(|l, r| l.0.cmp(&r.0));
    data.dedup();
    // Write
    let mut csv_file = fs::File::create(file_name)?;
    // header
    let mut header_keys: Vec<(&String, &usize)> =
        result_key_order.iter().collect::<Vec<(&String, &usize)>>();
    header_keys.sort_by_key(|e| e.1);
    let header_keys: Vec<String> = header_keys.iter().map(|e| e.0.clone()).collect();
    writeln!(csv_file, "t,{}", header_keys.join(","))?;
    // data
    for e in data.iter() {
        let key_order: usize = result_key_order[&e.2];
        writeln!(
            csv_file,
            "{},{}{}{}",
            e.0,
            ",".repeat(key_order),
            e.1,
            ",".repeat(result_key_order.len() - 1 - key_order),
        )?;
    }
    info!("Generated {file_name}");
    Ok(())
}

fn result_key_order(results: &[BluebenchResult]) -> HashMap<String, usize> {
    let mut result_keys = BTreeSet::<String>::new();
    let mut result_key_counts = HashMap::<String, usize>::new();
    for r in results.iter() {
        result_keys.insert(r.metadata.key.clone());
        result_key_counts.insert(
            r.metadata.key.clone(),
            result_key_counts.get(&r.metadata.key).unwrap_or(&0) + 1,
        );
    }
    let mut result_key_order = HashMap::<String, usize>::new();
    for (i, k) in result_keys.iter().enumerate() {
        info!("index {i}: {k} has {} valid results", result_key_counts[k]);
        result_key_order.insert(k.to_string(), i);
    }
    result_key_order
}

fn write_results(results: Vec<BluebenchResult>) -> Result<()> {
    info!(
        "{} succesfull test results in the specified range",
        results.len()
    );
    let result_key_order = result_key_order(&results);
    write_latency_csv(&results, &result_key_order)?;
    write_temp_csv(
        &results,
        &result_key_order,
        "x86_pkg_temp_C",
        "x86_pkg_temp.csv",
    )?;
    write_temp_csv(&results, &result_key_order, "TSR0_C", "tsr0_temp.csv")?;
    write_temp_csv(&results, &result_key_order, "TSR1_C", "tsr1_temp.csv")?;
    write_temp_csv(&results, &result_key_order, "TSR2_C", "tsr2_temp.csv")?;
    write_temp_csv(&results, &result_key_order, "TSR3_C", "tsr3_temp.csv")?;
    write_temp_csv(
        &results,
        &result_key_order,
        "TCPU_PCI_C",
        "tcpu_pci_temp.csv",
    )?;
    Ok(())
}

fn collect_candidates(args: &ArgsAnalyze) -> Result<Vec<PathBuf>> {
    let results_dir = match (&args.cros, &args.results_dir) {
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
    let start = args.start.clone().unwrap_or("0".to_string());
    let start = OsStr::new(&start);
    let end = args.end.clone().unwrap_or("9".to_string());
    let end = OsStr::new(&end);
    let results: Vec<PathBuf> = results
        .iter()
        .filter(|f| -> bool {
            if let Some(f) = f.file_name() {
                start <= f && f < end
            } else {
                false
            }
        })
        .cloned()
        .collect();
    info!("{} test results in the specified range", results.len());

    Ok(results)
}

fn dump_result(result: &BluebenchResult) -> Result<()> {
    info!("{:?} {:?}", result.metadata, result.converged_mean_mean);
    Ok(())
}

fn generate(args: &ArgsAnalyze, test_name: &str) -> Result<()> {
    let results = collect_candidates(args)?;
    if args.test {
        let results = analyze_latest_succesfull(results, test_name);
        for result in &results {
            dump_result(result)?;
        }
    } else {
        let results = analyze_all(results, test_name, args.hwid.as_deref());
        write_results(results)?;
    }
    Ok(())
}

#[derive(PartialEq, Eq, Debug, Hash, PartialOrd, Ord)]
struct HardwareInfo {
    hwid: String,
    serial_number: String,
    cpu_product_name: String,
    cpu_bugs: String,
}
impl HardwareInfo {
    pub fn parse(path: &Path, test_name: &str) -> Result<Self> {
        let hwid = BluebenchMetadata::hwid(path, test_name)?;
        let serial_number = BluebenchMetadata::serial_number(path, test_name)?;
        let cpu_product_name =
            BluebenchMetadata::cpu_product_name(path, test_name).unwrap_or("N/A".to_string());
        let cpu_bugs = BluebenchMetadata::cpu_bugs(path, test_name).unwrap_or("N/A".to_string());
        Ok(Self {
            hwid,
            serial_number,
            cpu_product_name,
            cpu_bugs,
        })
    }
}

fn hwid_and_info_map(
    args: &ArgsAnalyze,
    test_name: &str,
) -> Result<HashMap<String, HashSet<HardwareInfo>>> {
    let results = collect_candidates(args)?;
    let mut list: Vec<(String, HardwareInfo)> = results
        .par_iter()
        .map(|e| {
            let info = HardwareInfo::parse(e, test_name);
            info.map(|info| (info.hwid.clone(), info)).or(Err(()))
        })
        .flatten()
        .collect();
    list.sort();
    list.dedup();
    let mut dict = HashMap::new();
    for e in list {
        let hwid = &e.0;
        let serial = e.1;
        if !dict.contains_key(hwid) {
            dict.insert(hwid.clone(), HashSet::new());
        }
        (*dict.get_mut(hwid).unwrap()).insert(serial);
    }
    Ok(dict)
}

fn handle_write(stream: &TcpStream, path: &str) -> Result<()> {
    let mut res = BufWriter::new(stream);
    match path {
        // Bundled files
        "/" | "/index.html" => {
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_200_OK)?;
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_HTML_UTF8)?;
            writeln!(res)?;
            res.write_all(include_bytes!("../../assets/index.html"))?;
        }
        "/index.js" => {
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_200_OK)?;
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_JS_UTF8)?;
            writeln!(res)?;
            res.write_all(include_bytes!("../../assets/index.js"))?;
        }
        "/index.css" => {
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_200_OK)?;
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_CSS_UTF8)?;
            writeln!(res)?;
            res.write_all(include_bytes!("../../assets/index.css"))?;
        }
        "/third_party/dygraph.js" => {
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_200_OK)?;
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_JS_UTF8)?;
            writeln!(res)?;
            res.write_all(include_bytes!("../../third_party/dygraph.js"))?;
        }
        "/third_party/synchronizer.js" => {
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_200_OK)?;
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_JS_UTF8)?;
            writeln!(res)?;
            res.write_all(include_bytes!("../../third_party/synchronizer.js"))?;
        }
        "/third_party/dygraph.css" => {
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_200_OK)?;
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_CSS_UTF8)?;
            writeln!(res)?;
            res.write_all(include_bytes!("../../third_party/dygraph.css"))?;
        }
        // Data from the local path
        path if RE_CSV_PATH.is_match(path) => {
            let data = fs::read_to_string(&path[1..])?;
            let data = data.as_bytes();
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_200_OK)?;
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_KEEP_ALIVE)?;
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_CSV_UTF8)?;
            writeln!(res, "Content-Length: {}", data.len())?;
            writeln!(res)?;
            info!("path = {path:?}: Content length: {}", data.len());
            res.write_all(data)?;
        }
        "/data.json" => {
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_200_OK)?;
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_JSON_UTF8)?;
            writeln!(res)?;
            write!(res, "{}", fs::read_to_string("data.json")?.as_str())?;
        }
        _ => {
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_404_NOT_FOUND)?;
            writeln!(res, "{}", HTTP_RESPONSE_HEADER_HTML_UTF8)?;
            writeln!(res)?;
            writeln!(res, "404 Not Found")?;
        }
    };
    res.flush().context("Failed to flash the response")
}

/// Returns requested path
fn handle_read(mut stream: &TcpStream) -> Result<String> {
    let mut buf = [0u8; 4096];
    let len = stream.read(&mut buf)?;
    let req = String::from_utf8_lossy(&buf[..len]);
    let path = req
        .split(' ')
        .map(str::to_string)
        .nth(1)
        .context("Path should be specified");
    info!("path = {path:?}");
    path
}

fn handle_client(mut stream: TcpStream) -> Result<()> {
    stream.set_nodelay(true)?;
    let path = handle_read(&stream)?;
    if handle_write(&stream, &path).is_err() {
        writeln!(stream, "{}", HTTP_RESPONSE_HEADER_404_NOT_FOUND)?;
        writeln!(stream, "{}", HTTP_RESPONSE_HEADER_HTML_UTF8)?;
        writeln!(stream)?;
        writeln!(stream, "404 Not Found")?;
    }
    stream.flush()?;
    stream.set_read_timeout(Some(std::time::Duration::from_millis(1000)))?;
    let _ = stream.read(&mut [0; 128]);
    // No need to handle the error, but read is needed for reliable transfer...
    Ok(())
}

fn listen_http(port: u16) -> Result<()> {
    let listener = TcpListener::bind(format!("127.0.0.1:{port}")).unwrap();
    info!("Listening on port {port}");
    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                spawn(|| {
                    if let Err(e) = handle_client(stream) {
                        error!("handle_client failed: {e:?}");
                    }
                });
            }
            Err(e) => {
                error!("Incoming stream failed: {e:?}");
            }
        }
    }
    Ok(())
}
