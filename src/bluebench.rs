// Copyright 2024 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::collections::HashMap;
use std::fmt::Debug;
use std::fs;
use std::path::Path;

use anyhow::anyhow;
use anyhow::bail;
use anyhow::Context;
use anyhow::Result;
use lazy_static::lazy_static;
use regex::Regex;
use serde::Deserialize;
use serde::Serialize;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct BluebenchCycleResult {
    pub date: String,
    pub iter_index: usize,
    pub status: String,
    pub converged_mean: Option<f64>,
    pub t1: Option<f64>,
    pub t2: Option<f64>,
    pub t3: Option<f64>,
    pub raw: Vec<f64>,
}

lazy_static! {
    static ref RE_CSV_PATH: Regex = Regex::new(r"^/[A-Za-z0-9_.]+.csv$").unwrap();
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct BluebenchMetadata {
    pub path: String,
    pub key: String,
    pub dut_id: String,
    pub hwid: String,
    pub kernel_version: String,
    pub os_release: String,
    pub bootid: String,
    pub kernel_cmdline_mitigations: String,
    pub temperature_sensor_readouts: HashMap<String, Vec<(String, f64)>>,
    pub test_start_timestamp: String,
    pub test_end_timestamp: String,
}
impl BluebenchMetadata {
    pub fn parse_cpu_product_name(path: &Path, test_name: &str) -> Result<String> {
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
    pub fn parse_cpu_bugs(path: &Path, test_name: &str) -> Result<String> {
        let path = path.join("tests").join(test_name).join("cpuinfo.txt");
        let text = fs::read_to_string(&path).context(anyhow!("Failed to read {path:?}"))?;
        let lines: Vec<&str> = text.split('\n').collect();
        let lines: Vec<&&str> = lines.iter().filter(|s| s.starts_with("bugs")).collect();
        let line = lines.last().context("no text found")?;
        let line = line.split(':').nth(1).context("invalid cpu model name")?;
        let line = line.trim();
        Ok(line.to_string())
    }
    pub fn parse_serial_number(path: &Path, test_name: &str) -> Result<String> {
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
    pub fn parse_hwid(path: &Path, test_name: &str) -> Result<String> {
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
    pub fn parse_temp_log_line(s: &str) -> Result<(String, HashMap<String, f64>)> {
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
    pub fn temperature_sensor_readouts(
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
    pub fn test_start_end_timestamp(path: &Path, test_name: &str) -> Result<(String, String)> {
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
    pub fn from_path(path: &Path, test_name: &str, with_temp_data: bool) -> Result<Self> {
        let dut_id = Self::parse_serial_number(path, test_name)
            .or_else(|_| Result::<String>::Ok("NoSerial".to_string()))?;
        let hwid = Self::parse_hwid(path, test_name)?;
        let (test_start_timestamp, test_end_timestamp) =
            Self::test_start_end_timestamp(path, test_name)?;
        let kernel_version = Self::kernel_version(path, test_name)?;
        let os_release = Self::os_release(path, test_name)?;
        let bootid = Self::bootid(path, test_name)?;
        let kernel_cmdline_mitigations = Self::kernel_cmdline_mitigations(path, test_name)?;
        let temperature_sensor_readouts = if with_temp_data {
            Self::temperature_sensor_readouts(
                path,
                test_name,
                &test_start_timestamp,
                &test_end_timestamp,
            )?
        } else {
            HashMap::new()
        };
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

#[derive(Serialize, Deserialize, Clone)]
pub struct BluebenchResult {
    pub metadata: BluebenchMetadata,
    pub last_result_date: String,
    pub converged_mean_mean: f64,
    pub cycles: Vec<BluebenchCycleResult>,
}
impl Debug for BluebenchResult {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "BluebenchResult {{ metadata: {:?}, converged_mean_mean: {:?} }}",
            self.metadata, self.converged_mean_mean
        )
    }
}
impl BluebenchResult {
    pub fn from_path(path: &Path) -> Result<Self> {
        let test_name = "perf.TabOpenLatencyPerf";
        let metadata = BluebenchMetadata::from_path(path, test_name, false)?;
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
        let converged_mean_mean =
            converged_means.iter().sum::<f64>() / converged_means.len() as f64;
        let last_result_date = cycles.last().unwrap().date.clone();
        Ok(BluebenchResult {
            metadata,
            last_result_date,
            cycles,
            converged_mean_mean,
        })
    }
}
