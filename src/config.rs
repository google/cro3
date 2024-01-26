// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::collections::HashMap;
use std::fs::read_to_string;
use std::fs::write;

use anyhow::anyhow;
use anyhow::bail;
use anyhow::Context;
use anyhow::Result;
use regex::Regex;
use serde::Deserialize;
use serde::Serialize;
use tracing::warn;

use crate::util::lium_paths::gen_path_in_lium_dir;
use crate::util::shell_helpers::run_bash_command;

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
    android_branches: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    android_manifest_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    default_cros_checkout: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    default_cros_reference: Option<String>,
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
    /// This config option indicates that you are an internal user. When it is
    /// true, the behavior of this tool will be optimized for the internal users
    /// by default (e.g. using internal manifest for checking out source code by
    /// default). It is false by default.
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    is_internal: Option<bool>,
    /// Command to check if internal authentication valid. It is set by the
    /// internal lium-installer.
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    is_internal_auth_valid: Option<String>,
    /// Path to acloudw.sh. It is set by the internal lium-installer.
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    acloudw_cmd_path: Option<String>,
    /// Path to acloudw config file. It is set by the internal lium-installer.
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    acloudw_config_path: Option<String>,
    /// Key: {vm, container, main}, value: Android lunch target. It is set by
    /// the internal lium-installer.
    #[serde(skip_serializing_if = "HashMap::is_empty")]
    #[serde(default)]
    android_target_for_vm_type: HashMap<String, String>,
    /// Command to get cheeps image name for ARCVM. It is set by the internal
    /// lium-installer.
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    arc_vm_cheeps_image: Option<String>,
    /// Key: Android branch, value: command to get betty image name for ARCVM.
    /// It is set by the internal lium-installer.
    #[serde(skip_serializing_if = "HashMap::is_empty")]
    #[serde(default)]
    arc_vm_betty_image_for_branch: HashMap<String, String>,
    /// Key: Android branch, value: command to get cheeps image name for
    /// ARC-container. It is set by the internal lium-installer.
    #[serde(skip_serializing_if = "HashMap::is_empty")]
    #[serde(default)]
    arc_container_cheeps_image_for_branch: HashMap<String, String>,
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
                warn!("config file created at {:?}", path);
                Ok(config)
            }
            e => bail!("Failed to create a new config: {:?}", e),
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
            "android_branches" => {
                let branches: Vec<String> =
                    values[0..].iter().map(|s| s.as_ref().to_string()).collect();
                self.android_branches = Some(branches);
            }
            "android_manifest_url" => {
                if values.len() != 1 {
                    bail!("{key} only takes 1 params");
                }
                self.android_manifest_url = Some(values[0].as_ref().to_string());
            }
            "default_cros_checkout" => {
                if values.len() != 1 {
                    bail!("{key} only takes 1 params");
                }
                self.default_cros_checkout = Some(values[0].as_ref().to_string());
            }
            "default_cros_reference" => {
                if values.len() != 1 {
                    bail!("{key} only takes 1 params");
                }
                self.default_cros_reference = Some(values[0].as_ref().to_string());
            }
            "ssh_override" => {
                if values.len() < 3 {
                    bail!("{key} takes 3+ parameters");
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
                    bail!("{key} only takes 1 params");
                }
                self.ssh_port_search_timeout = Some(values[0].as_ref().parse().unwrap());
            }
            "default_ipv6_prefix" => {
                if values.len() != 1 {
                    bail!("{key} only takes 1 params");
                }
                self.default_ipv6_prefix = Some(values[0].as_ref().parse().unwrap());
            }
            "is_internal" => {
                if values.len() != 1 {
                    bail!("{key} only takes 1 params");
                }
                self.is_internal = Some(values[0].as_ref().parse::<bool>().unwrap());
            }
            "is_internal_auth_valid" => {
                if values.len() != 1 {
                    bail!("{key} only takes 1 params");
                }
                self.is_internal_auth_valid = Some(values[0].as_ref().to_string());
            }
            "acloudw_cmd_path" => {
                if values.len() != 1 {
                    bail!("{key} only takes 1 params");
                }
                self.acloudw_cmd_path = Some(values[0].as_ref().to_string());
            }
            "acloudw_config_path" => {
                if values.len() != 1 {
                    bail!("{key} only takes 1 params");
                }
                self.acloudw_config_path = Some(values[0].as_ref().to_string());
            }
            "android_target_for_vm_type" => {
                if values.len() != 2 {
                    bail!("{key} takes 2 parameters");
                }
                let branch = values[0].as_ref().to_string();
                let target = values[1].as_ref().to_string();
                self.android_target_for_vm_type.insert(branch, target);
            }
            "arc_vm_cheeps_image" => {
                if values.len() != 1 {
                    bail!("{key} only takes 1 params");
                }
                self.arc_vm_cheeps_image = Some(values[0].as_ref().to_string());
            }
            "arc_vm_betty_image_for_branch" => {
                if values.len() != 2 {
                    bail!("{key} takes 2 parameters");
                }
                let branch = values[0].as_ref().to_string();
                let target = values[1].as_ref().to_string();
                self.arc_vm_betty_image_for_branch.insert(branch, target);
            }
            "arc_container_cheeps_image_for_branch" => {
                if values.len() != 2 {
                    bail!("{key} takes 2 parameters");
                }
                let branch = values[0].as_ref().to_string();
                let target = values[1].as_ref().to_string();
                self.arc_container_cheeps_image_for_branch
                    .insert(branch, target);
            }
            _ => bail!("config key {key} is not valid"),
        }
        self.write()
    }
    pub fn clear(&mut self, key: &str) -> Result<()> {
        match key {
            "android_branches" => {
                self.android_branches = None;
            }
            "android_manifest_url" => {
                self.android_manifest_url = None;
            }
            "default_cros_checkout" => {
                self.default_cros_checkout = None;
            }
            "default_cros_reference" => {
                self.default_cros_reference = None;
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
            "is_internal" => {
                self.is_internal = None;
            }
            "is_internal_auth_valid" => {
                self.is_internal_auth_valid = None;
            }
            "acloudw_cmd_path" => {
                self.acloudw_cmd_path = None;
            }
            "acloudw_config_path" => {
                self.acloudw_config_path = None;
            }
            "android_target_for_vm_type" => self.android_target_for_vm_type.clear(),
            "arc_vm_cheeps_image" => {
                self.arc_vm_cheeps_image = None;
            }
            "arc_vm_betty_image_for_branch" => self.arc_vm_betty_image_for_branch.clear(),
            "arc_container_cheeps_image_for_branch" => {
                self.arc_container_cheeps_image_for_branch.clear()
            }
            _ => bail!("lium config clear for '{key}' is not implemented"),
        }
        self.write()?;
        Ok(())
    }
    pub fn android_branches(&self) -> Vec<&str> {
        if let Some(branches) = &self.android_branches {
            branches.iter().map(|s| s as &str).collect()
        } else {
            Vec::new()
        }
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
    pub fn default_cros_reference(&self) -> Option<String> {
        self.default_cros_reference.clone()
    }
    pub fn ssh_port_search_timeout(&self) -> u64 {
        self.ssh_port_search_timeout.unwrap_or(60 /* 1 min */)
    }
    pub fn default_ipv6_prefix(&self) -> Option<String> {
        self.default_ipv6_prefix.clone()
    }
    pub fn is_internal(&self) -> bool {
        self.is_internal.unwrap_or(false)
    }
    pub fn is_internal_auth_valid(&self) -> Option<String> {
        self.is_internal_auth_valid.clone()
    }
    pub fn acloudw_cmd_path(&self) -> Option<String> {
        self.acloudw_cmd_path.clone()
    }
    pub fn acloudw_config_path(&self) -> Option<String> {
        self.acloudw_config_path.clone()
    }
    pub fn android_target_for_vm_type(&self) -> &HashMap<String, String> {
        &self.android_target_for_vm_type
    }
    pub fn arc_vm_cheeps_image(&self) -> Option<String> {
        self.arc_vm_cheeps_image.clone()
    }
    pub fn arc_vm_betty_image_for_branch(&self) -> &HashMap<String, String> {
        &self.arc_vm_betty_image_for_branch
    }
    pub fn arc_container_cheeps_image_for_branch(&self) -> &HashMap<String, String> {
        &self.arc_container_cheeps_image_for_branch
    }
}
