// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use crate::util::gen_path_in_lium_dir;
use crate::util::run_bash_command;
use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use regex::Regex;
use serde::Deserialize;
use serde::Serialize;
use std::collections::HashMap;
use std::fs::read_to_string;
use std::fs::write;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SshOverride {
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    shell_condition: Option<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    #[serde(default)]
    ssh_options: Vec<String>,
}
impl SshOverride {
    pub fn is_match_condition(&self) -> Result<bool> {
        if let Some(cmd) = &self.shell_condition {
            Ok(run_bash_command(cmd, None)?.status.success())
        } else {
            // Return true always if shell_condition is not specified
            Ok(true)
        }
    }
    pub fn ssh_options(&self) -> &Vec<String> {
        &self.ssh_options
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Config {
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    android_manifest_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    default_cros_checkout: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    default_cros_mirror: Option<String>,
    #[serde(skip_serializing_if = "HashMap::is_empty")]
    #[serde(default)]
    ssh_overrides: HashMap<String, SshOverride>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    tast_bundles: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    ssh_port_search_timeout: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    default_ipv6_prefix: Option<String>,
}
static CONFIG_FILE_NAME: &str = "config.json";
impl Config {
    pub fn read() -> Result<Self> {
        let path = gen_path_in_lium_dir(CONFIG_FILE_NAME)?;
        let config = read_to_string(&path);
        match config {
            Ok(config) => Ok(serde_json::from_str(&config)?),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                // Just create a default config
                let config = Self::default();
                config.write()?;
                eprintln!("INFO: config file created at {:?}", path);
                Ok(config)
            }
            e => Err(anyhow!("Failed to create a new config: {:?}", e)),
        }
    }
    // This is private since write should happen on every updates transparently
    fn write(&self) -> Result<()> {
        let s = serde_json::to_string_pretty(&self)?;
        write(gen_path_in_lium_dir(CONFIG_FILE_NAME)?, s.into_bytes())
            .context("failed to write config")
    }
    pub fn set<K: AsRef<str>>(&mut self, key: &str, values: &[K]) -> Result<()> {
        match key {
            "android_manifest_url" => {
                if values.len() != 1 {
                    return Err(anyhow!("{key} only takes 1 params"));
                }
                self.android_manifest_url = Some(values[0].as_ref().to_string());
            }
            "default_cros_checkout" => {
                if values.len() != 1 {
                    return Err(anyhow!("{key} only takes 1 params"));
                }
                self.default_cros_checkout = Some(values[0].as_ref().to_string());
            }
            "default_cros_mirror" => {
                if values.len() != 1 {
                    return Err(anyhow!("{key} only takes 1 params"));
                }
                self.default_cros_mirror = Some(values[0].as_ref().to_string());
            }
            "ssh_override" => {
                if values.len() < 3 {
                    return Err(anyhow!("{key} takes 3+ parameters"));
                }
                let host_regex = values[0].as_ref().to_string();
                Regex::new(&host_regex).context("Invalid regex is provided as a host_pattern")?;
                let shell_condition = Some(values[1].as_ref().to_string());
                let ssh_options: Vec<String> =
                    values[2..].iter().map(|s| s.as_ref().to_string()).collect();
                self.ssh_overrides.insert(
                    host_regex,
                    SshOverride {
                        shell_condition,
                        ssh_options,
                    },
                );
            }
            "tast_bundles" => {
                let bundles: Vec<String> =
                    values[0..].iter().map(|s| s.as_ref().to_string()).collect();
                self.tast_bundles = Some(bundles);
            }
            "ssh_port_search_timeout" => {
                if values.len() != 1 {
                    return Err(anyhow!("{key} only takes 1 params"));
                }
                self.ssh_port_search_timeout = Some(values[0].as_ref().parse().unwrap());
            }
            "default_ipv6_prefix" => {
                if values.len() != 1 {
                    return Err(anyhow!("{key} only takes 1 params"));
                }
                self.default_ipv6_prefix = Some(values[0].as_ref().parse().unwrap());
            }
            _ => return Err(anyhow!("config key {key} is not valid")),
        }
        self.write()
    }
    pub fn clear(&mut self, key: &str) -> Result<()> {
        match key {
            "android_manifest_url" => {
                self.android_manifest_url = None;
            }
            "default_cros_checkout" => {
                self.default_cros_checkout = None;
            }
            "default_cros_mirror" => {
                self.default_cros_mirror = None;
            }
            "ssh_overrides" => self.ssh_overrides.clear(),
            "ssh_override" => {
                return Err(anyhow!(
                    "please use `lium config clear ssh_overrides` instead ;)"
                ))
            }
            "tast_bundles" => {
                self.tast_bundles = None;
            }
            "ssh_port_search_timeout" => {
                self.ssh_port_search_timeout = None;
            }
            "default_ipv6_prefix" => {
                self.default_ipv6_prefix = None;
            }
            _ => return Err(anyhow!("lium config clear for '{key}' is not implemented")),
        }
        self.write()?;
        Ok(())
    }
    pub fn tast_bundles(&self) -> Vec<&str> {
        if let Some(bundles) = &self.tast_bundles {
            bundles.iter().map(|s| s as &str).collect()
        } else {
            Vec::new()
        }
    }
    pub fn ssh_overrides(&self) -> &HashMap<String, SshOverride> {
        &self.ssh_overrides
    }
    pub fn android_manifest_url(&self) -> Option<String> {
        self.android_manifest_url.clone()
    }
    pub fn default_cros_checkout(&self) -> Option<String> {
        self.default_cros_checkout.clone()
    }
    pub fn ssh_port_search_timeout(&self) -> Option<u64> {
        self.ssh_port_search_timeout
    }
    pub fn default_ipv6_prefix(&self) -> Option<String> {
        self.default_ipv6_prefix.clone()
    }
}
