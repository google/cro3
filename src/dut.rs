// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::collections::HashMap;
use std::collections::HashSet;
use std::env::current_exe;
use std::ffi::OsStr;
use std::ops::RangeInclusive;
use std::process::Command;
use std::process::Output;
use std::process::Stdio;
use std::str::FromStr;
use std::time::Duration;

use anyhow::anyhow;
use anyhow::bail;
use anyhow::Context;
use anyhow::Result;
use base64::engine::general_purpose::STANDARD;
use base64::Engine;
use chrono::Local;
use futures::executor::block_on;
use futures::select;
use futures::stream;
use futures::StreamExt;
use lazy_static::lazy_static;
use rand::seq::SliceRandom;
use rand::thread_rng;
use rayon::prelude::*;
use regex::Regex;
use retry::retry;
use serde::{Deserialize, Serialize};
use tracing::error;
use tracing::info;
use url::Url;

use crate::cache::KvCache;
use crate::config::Config;
use crate::cros::ensure_testing_rsa_is_there;
use crate::util::shell_helpers::get_async_lines;
use crate::util::shell_helpers::get_stderr;
use crate::util::shell_helpers::get_stdout;
use crate::util::shell_helpers::run_bash_command;

const COMMON_SSH_OPTIONS: [&str; 16] = [
    // Do not read ~/.ssh/config to avoid effects comes from ssh_config
    "-F",
    "none",
    // Use CrOS testing_rsa as a key
    "-i",
    "~/.ssh/testing_rsa",
    // Enable batchmode to disable interactive auth
    "-o",
    "BatchMode=yes",
    // Do not check host key since it can change easily during development
    "-o",
    "StrictHostKeyChecking=no",
    // Do not record or verify the known hosts
    "-o",
    "UserKnownHostsFile=/dev/null",
    // Silence the "Warning: Permanently added ... to the list of known hosts" message
    "-o",
    "LogLevel=ERROR",
    // Set connection timeout to give up quickly
    "-o",
    "ConnectTimeout=5",
    // Try pubkey auth only
    "-o",
    "PreferredAuthentications=publickey",
];

lazy_static! {
    static ref RE_IPV6_WITH_BRACKETS: Regex = Regex::new(r"^\[(?P<addr>[0-9a-fA-F:]+(%.*)?)\]$").unwrap();
    // based on https://url.spec.whatwg.org/#host-miscellaneous
    static ref RE_DUT_HOST_NAME: Regex =
        Regex::new(r"^(([0-9.]+)|([0-9a-fA-F:]+(%.*)?)|([^\t\n\r #/:<>?@\[\]^|]+))$").unwrap();
    static ref RE_GBB_FLAGS: Regex =
        Regex::new(r"^0x[0-9a-fA-F]+$").unwrap();
}

pub static SSH_CACHE: KvCache<SshInfo> = KvCache::new("ssh_cache");

pub enum PartitionSet {
    Primary,
    Secondary,
}

/// MonitoredDut holds connection to a monitoring Dut
#[derive(Debug)]
pub struct MonitoredDut {
    ssh: SshInfo,
    dut: String,
    port: u16,
    child: Option<async_process::Child>,
    reconnecting: bool,
}
impl MonitoredDut {
    pub fn new(dut: &str, port: u16) -> Result<Self> {
        let ssh = SshInfo::new(dut).context("failed to create SshInfo")?;
        let dut = MonitoredDut {
            ssh: ssh.clone(),
            dut: dut.to_string(),
            port,
            child: block_on(ssh.start_ssh_forwarding(port)).ok(),
            reconnecting: false,
        };
        Ok(dut)
    }
    pub fn reconnecting(&self) -> bool {
        self.reconnecting
    }
    fn reconnect(&mut self) -> Result<String> {
        let new_child = block_on(self.ssh.start_ssh_forwarding(self.port));
        if let Err(e) = &new_child {
            error!("Failed to reconnect: {e:?}");
        };
        self.child = new_child.ok();
        self.reconnecting = true;
        Ok(format!("{:<31}\tReconnecting...", &self.dut))
    }
    pub fn get_status_header() -> String {
        format!("{:<31}\t{:<15}\t{}", "DUT", "Forward Addr", "IP Addr")
    }
    pub fn get_status(&mut self) -> Result<String> {
        if let Some(child) = &mut self.child {
            match child.try_status()? {
                None => {
                    self.reconnecting = false;
                    Ok(format!(
                        "{:<31}\t127.0.0.1:{:<5}\t{}",
                        &self.dut,
                        self.port,
                        &self.ssh.host_and_port()
                    ))
                }
                Some(_status) => self.reconnect(),
            }
        } else {
            self.reconnect()
        }
    }
}

lazy_static! {
    // We cannot use `grep -Po` here since some machines have grep built with --disable-perl-regexp
    static ref DUT_ATTRIBUTE_CMDS: HashMap<&'static str, &'static str> = {
        let mut m: HashMap<&'static str, &'static str> = HashMap::new();
        m.insert("board", r"cat /etc/lsb-release | grep CHROMEOS_RELEASE_BOARD | cut -d '=' -f 2 | cut -d '-' -f 1");
        // NOTE: VM instances do not have a valid HWID.
        m.insert("hwid", r"crossystem hwid");
        m.insert("arch", r"crossystem arch");
        m.insert("serial", r"vpd -g serial_number");
        m.insert("model_from_cros_config", r"cros_config / name");
        m.insert("model_from_mosys", r"mosys platform name");
        m.insert("ectool_temps_all", r"ectool temps all");
        m.insert(
            "gbb_flags",
            // get_gbb_flags.sh is deprecated but keeping this usage for backwards compatibility.
            // Newer scripts should use futility instead (see above). b/269179419 for more info.
            r"{ /usr/bin/futility gbb --flash --get --flags | grep 'flags: ' || /usr/share/vboot/bin/get_gbb_flags.sh | grep 'Chrome OS GBB' ; } | cut -d : -f 2",
        );
        m.insert(
            "host_kernel_config",
            r"modprobe configs; zcat /proc/config.gz",
        );
        m.insert("lshw", r"lshw -json");
        m.insert("lsb_release", r"cat /etc/lsb-release");
        m.insert("ipv6_addr", concat!(r"ip -6 address show dev `cro3_get_default_iface` mngtmpaddr | grep inet6 | sed -E 's/\s+/ /g' | tr '/' ' ' | cut -d ' ' -f 3"));
        m.insert("ipv4_addr", r"ip -4 address show dev `cro3_get_default_iface` scope global | grep inet | sed -E 's/\s+/ /g' | tr '/' ' ' | cut -d ' ' -f 3");
        m.insert("ipv6_addrs", r"ip -6 address show dev `cro3_get_default_iface` mngtmpaddr | grep inet6 | sed -E 's/\s+/ /g' | tr '/' ' ' | cut -d ' ' -f 3");
        m.insert("mac", r"ip addr show dev `cro3_get_default_iface` | grep ether | grep -E -o '([0-9a-z]{2}:){5}([0-9a-z]{2})' | head -n 1");
        m.insert("release", r"cat /etc/lsb-release | grep CHROMEOS_RELEASE_DESCRIPTION | sed -e 's/CHROMEOS_RELEASE_DESCRIPTION=//'");
        m.insert("dev_boot_usb", r"crossystem dev_boot_usb");
        m.insert("dev_default_boot", r"crossystem dev_default_boot");
        m.insert("fwid", r"crossystem fwid");
        m.insert("ro_fwid", r"crossystem ro_fwid");
        m.insert("uptime", r"cat /proc/uptime | cut -d ' ' -f 2");
        m.insert("ectool_temps_all", r"ectool temps all");
        m
    };
}

const CMD_GET_DEFAULT_IFACE: &str =
    r"ip route get 8.8.8.8 | sed -E 's/^.* dev ([^ ]+) .*$/\1/' | head -n 1";

// Only keys that are always available can be listed here
const DEFAULT_DUT_INFO_KEYS: [&str; 7] = [
    "timestamp",
    "dut_id",
    "release",
    "model",
    "serial",
    "board",
    "mac",
];

/// DutInfo holds information around a DUT
#[derive(Debug, Clone)]
pub struct DutInfo {
    key: KeyInfo,
    ssh: SshInfo,
    info: HashMap<String, String>,
}
impl DutInfo {
    async fn from_ssh(ssh: &SshInfo, extra_attr: &[String]) -> Result<Self> {
        let info = Self::fetch_keys(
            ssh,
            &[
                DEFAULT_DUT_INFO_KEYS.to_vec(),
                extra_attr.iter().map(|s| s.as_str()).collect(),
            ]
            .concat(),
        )?;
        let key = KeyInfo::from_raw_dut_info(&info)
            .await
            .context("failed to get key")?;
        let dut = DutInfo {
            key,
            ssh: ssh.clone(),
            info,
        };
        SSH_CACHE.set(dut.id(), ssh.clone())?;
        Ok(dut)
    }
    /// new should be fast enough (less than a sec per a DUT)
    pub fn new(dut: &str) -> Result<Self> {
        let ssh = SshInfo::new(dut).context("failed to create SshInfo")?;
        block_on(Self::from_ssh(&ssh, &Vec::new()))
    }
    pub fn new_host_and_port(host: &str, port: u16) -> Result<Self> {
        let ssh = SshInfo::new_host_and_port(host, port).context("failed to create SshInfo")?;
        block_on(Self::from_ssh(&ssh, &Vec::new()))
    }
    pub fn id(&self) -> &str {
        self.key.key()
    }
    pub fn ssh(&self) -> &SshInfo {
        &self.ssh
    }
    pub fn info(&self) -> &HashMap<String, String> {
        &self.info
    }
    /// To avoid problems around shell escapes and make it easy to parse,
    /// using base64 here to run the commands.
    fn gen_cmd_for_key(key: &str) -> Result<String> {
        let cmd = *DUT_ATTRIBUTE_CMDS
            .get(key)
            .context(anyhow!("Unknown DUT attribute: {key}"))?;
        let cmd = STANDARD.encode(cmd);
        Ok(format!(
            r##"export tmp="$(mktemp -d)" && echo {cmd} | base64 -d | bash > $tmp/stdout 2>$tmp/stderr ; code=$? ; echo {key},$?,`cat $tmp/stdout | base64 -w 0`,`cat $tmp/stderr | base64 -w 0`"##
        ))
    }
    fn decode_result_line(s: &str, key: &str) -> Result<String> {
        let s = s.split(',').collect::<Vec<&str>>();
        if s.len() != 4 {
            bail!("4 elements are expected in a row but got: {s:?}");
        }
        if s[0] == key {
            let key = s[0].to_string();
            let exit_code = u8::from_str(s[1])?;
            let value = String::from_utf8(STANDARD.decode(s[2])?)?
                .trim()
                .to_string();
            let stderr = String::from_utf8(STANDARD.decode(s[3])?)?
                .trim()
                .to_string();
            if exit_code != 0 {
                Err(anyhow!(
                    "Command for key {key} exited with code {exit_code}"
                ))
            } else if value.is_empty() {
                bail!("key {key} found but was empty. stderr: {stderr}")
            } else {
                Ok(value)
            }
        } else {
            bail!("key {key} did not found. stderr")
        }
    }
    fn parse_values(
        keys: &[&str],
        mut values: HashMap<String, Result<String>>,
    ) -> Result<HashMap<String, String>> {
        // Construct values based on values
        if keys.contains(&"timestamp") {
            values.insert("timestamp".to_string(), Ok(Local::now().to_string()));
        }
        if keys.contains(&"model") {
            if let Some(Ok(model)) = values.get("model_from_cros_config") {
                values.insert("model".to_string(), Ok(model.clone()));
            } else if let Some(Ok(model)) = values.get("model_from_mosys") {
                values.insert("model".to_string(), Ok(model.clone()));
            } else {
                bail!("Failed to get model");
            }
        }
        if keys.contains(&"gbb_flags") {
            let gbb_flags = if let Some(Ok(v)) = values.get("gbb_flags") {
                v
            } else {
                bail!("Failed to get model");
            };
            if let Some(gbb_flags) = RE_GBB_FLAGS.find(gbb_flags) {
                values.insert("gbb_flags".to_string(), Ok(gbb_flags.as_str().to_string()));
            } else {
                return Err(anyhow!(
                    "gbb_flags should match regex RE_GBB_FLAGS but got {gbb_flags:?}"
                ));
            }
        }
        if keys.contains(&"dut_id") {
            let serial = if let Some(Ok(serial)) = values.get("serial") {
                serial.to_string()
            } else {
                // Some DUTs don't have serial number. So use MAC address,
                let serial = if let Some(Ok(mac)) = values.get("mac") {
                    format!("NoSerial{}", mac.replace(':', "").to_lowercase())
                } else {
                    return Err(anyhow!(
                        "Failed to get MAC address. {:?}",
                        values.get("mac")
                    ));
                };
                values.insert("serial".to_string(), Ok(serial.to_string()));
                serial
            };
            if let Some(Ok(model)) = values.get("model") {
                let dut_id = format!("{model}_{serial}");
                values.insert("dut_id".to_string(), Ok(dut_id));
            } else {
                bail!("Failed to get model. {:?}", values.get("model"));
            }
        }
        // Collect all values for given keys
        keys.iter()
            .map(|&k| {
                let v = values.get(k);
                if let Some(Ok(v)) = v {
                    Ok((k.to_string(), v.clone()))
                } else {
                    bail!("failed to get key {k}: {v:?}")
                }
            })
            .collect()
    }
    pub fn fetch_keys(ssh: &SshInfo, keys: &Vec<&str>) -> Result<HashMap<String, String>> {
        ensure_testing_rsa_is_there()?;
        // First, list up all the keys to retrieve from a DUT
        let mut keys_from_dut = HashSet::new();
        // Dependent variables
        for k in keys {
            match *k {
                "timestamp" => continue,
                "dut_id" => {
                    keys_from_dut.insert("ipv6_addr");
                    keys_from_dut.insert("serial");
                }
                "model" => {
                    keys_from_dut.insert("model_from_cros_config");
                    keys_from_dut.insert("model_from_mosys");
                }
                k => {
                    keys_from_dut.insert(k);
                }
            }
        }
        let cmds = format!(
            "function cro3_get_default_iface {{ {CMD_GET_DEFAULT_IFACE} ; }} && export -f \
             cro3_get_default_iface && "
        );
        let cmds = cmds
            + &keys_from_dut
                .iter()
                .map(|s| Self::gen_cmd_for_key(s))
                .collect::<Result<Vec<String>>>()?
                .join(" && ");

        info!("Fetching info for {:?}...", ssh);
        let result = ssh.run_cmd_stdio(&cmds)?;
        let values: HashMap<String, Result<String>> = result
            .split('\n')
            .zip(keys_from_dut.iter())
            .map(|(line, key)| -> (String, Result<String>) {
                let value = Self::decode_result_line(line, key);
                (key.to_string(), value)
            })
            .collect();
        Self::parse_values(keys, values)
    }
}

pub struct ForwardedDut {
    ssh: SshInfo,
    forwarding_process: Option<async_process::Child>,
}
impl ForwardedDut {
    pub fn ssh(&self) -> &SshInfo {
        &self.ssh
    }
}
impl Drop for ForwardedDut {
    fn drop(&mut self) {
        if let Some(forwarding_process) = &mut self.forwarding_process {
            info!("Sending SIGTERM to the forwarding process {}", forwarding_process.id());
            nix::sys::signal::kill(nix::unistd::Pid::from_raw(forwarding_process.id() as i32), nix::sys::signal::Signal::SIGTERM).expect("failed to kill");
        }
    }
}

/// SshInfo holds information needed to establish an ssh connection
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SshInfo {
    /// An IPv4 address, an IPv6 address or DNS name.
    /// IPv6 address MUST NOT not have brackets.
    host: String,
    port: u16,
}
impl SshInfo {
    pub fn ping(&self) -> Result<()> {
        let host = &self.host;
        let output = run_bash_command(&format!("ping -c 1 -W 0.5 {host} 1>/dev/null 2>&1"), None)?;
        output.status.exit_ok().context("Failed to ping")
    }
    pub fn new(dut: &str) -> Result<Self> {
        if let Ok(Some(resolved)) = SSH_CACHE.get(dut) {
            return Ok(resolved);
        }
        if dut.contains('_') {
            // '_' is a character that is not allowed for hostname.
            // Therefore, we can assume that unknown DUT ID is specified.
            return Err(anyhow!(
                "DUT {dut} is not cached yet. Please run `cro3 dut info ${{DUT_IP}}` first."
            ));
        }
        let url = "ssh://".to_string() + dut;
        // As https://url.spec.whatwg.org/#concept-ipv6 says,
        // > Support for <zone_id> is intentionally omitted.
        // So that we can not parse dut string like:
        // > [fe80::8a54:1fff:fe0f:72a5%en0]
        // TODO(hikalium): Impl workaround, possibly fix in the url crate.
        let url = Url::parse(&url).context(anyhow!("Failed to parse url: {url}"))?;
        let host = url.host_str().unwrap_or("127.0.0.1").to_string();
        let port = url.port().unwrap_or(22);
        Self::new_host_and_port(&host, port)
    }
    pub fn new_host_and_port(host: &str, port: u16) -> Result<Self> {
        let host = if let Some(c) = RE_IPV6_WITH_BRACKETS.captures(host) {
            c.name("addr").context("no addr matched")?.as_str()
        } else {
            host
        };
        if !RE_DUT_HOST_NAME.is_match(host) {
            Err(anyhow!(
                "Invalid hostname {:?}. A host name should match with: {:?}",
                host,
                RE_DUT_HOST_NAME.to_string()
            ))
        } else {
            Ok(Self {
                host: host.to_string(),
                port,
            })
        }
    }
    pub fn host(&self) -> &str {
        &self.host
    }
    pub fn needs_port_forwarding_in_chroot(&self) -> bool {
        self.host != "localhost" && self.host != "127.0.0.1"
    }
    pub fn port(&self) -> u16 {
        self.port
    }
    pub fn host_and_port(&self) -> String {
        let port = self.port;
        let host = &self.host;
        // If the address has ':', it must be enclosed in square brackets.
        if host.find(':').is_some() {
            format!("[{host}]:{port}")
        } else {
            format!("{host}:{port}")
        }
    }
    pub fn into_forwarded(&self) -> Result<ForwardedDut> {
        if self.needs_port_forwarding_in_chroot() {
            let (port, forwarding_process) = self.start_ssh_forwarding_background()?;
            let ssh = Self::new_host_and_port("127.0.0.1", port)?;
            Ok(ForwardedDut {
                ssh,
                forwarding_process: Some(forwarding_process),
            })
        } else {
            Ok(ForwardedDut {
                ssh: self.clone(),
                forwarding_process: None,
            })
        }
    }
    fn gen_ssh_options(&self) -> Result<Vec<String>> {
        let mut args: Vec<String> = Vec::from(COMMON_SSH_OPTIONS)
            .iter()
            .map(|s| s.to_string())
            .collect();
        let host = &self.host;
        let config = Config::read()?;
        for (k, v) in config.ssh_overrides() {
            if !Regex::new(k)
                .context("Failed to compile regex for ssh overrides")?
                .is_match(host)
                || !v.is_match_condition()?
            {
                continue;
            }
            args.extend(v.ssh_options().iter().map(|e| e.to_owned()));
        }
        Ok(args)
    }

    fn gen_ssh_args(&self, optional_args: Option<&[&str]>) -> Result<Vec<String>> {
        let mut args = self.gen_ssh_options()?;

        let host = &self.host.replace(['[', ']'], "");
        let port = self.port;
        let user = "root";
        let user_at_host = format!("{user}@{host}");
        let port = port.to_string();
        args.extend_from_slice(&["-p".to_string(), port]);
        if let Some(optional_args) = optional_args {
            args.extend(optional_args.iter().map(|s| s.to_string()));
        }
        args.extend_from_slice(&[user_at_host, "--".to_string()]);
        Ok(args)
    }

    fn gen_scp_get_args(&self, files: &[String], dest: Option<&String>) -> Result<Vec<String>> {
        let mut args = self.gen_ssh_options()?;

        let port = self.port.to_string();
        args.extend_from_slice(&["-P".to_string(), port]);

        // Recursive by default
        args.push("-r".to_string());

        let host = &self.host.replace(['[', ']'], "");
        let user = "root";
        let prefix = if host.find(':').is_some() {
            format!("{user}@[{host}]")
        } else {
            format!("{user}@{host}")
        };

        let mut args: Vec<String> = args.iter().map(|s| s.into()).collect();
        for src in files.iter().map(|p| format!("{prefix}:{p}")) {
            args.push(src);
        }

        let destdir = if let Some(d) = dest { d } else { "." };
        args.push(destdir.to_string());

        Ok(args)
    }
    fn gen_scp_send_args(&self, files: &[String], dest: Option<&String>) -> Result<Vec<String>> {
        let mut args = self.gen_ssh_options()?;

        args.extend_from_slice(&["-P".to_string(), self.port.to_string()]);

        // Recursive by default
        args.push("-r".to_string());

        let host = &self.host.replace(['[', ']'], "");
        let user = "root";
        let prefix = if host.find(':').is_some() {
            format!("{user}@[{host}]")
        } else {
            format!("{user}@{host}")
        };

        let mut args: Vec<String> = args.iter().map(|s| s.into()).collect();
        args.append(files.to_owned().as_mut());

        let destdir = if let Some(d) = dest { d } else { "~/" };
        args.push(format!("{prefix}:{destdir}"));

        Ok(args)
    }
    pub fn scp_get_cmd(&self, files: &[String], dest: Option<&String>) -> Result<Command> {
        let mut cmd = Command::new("scp");
        cmd.args(self.gen_scp_get_args(files, dest)?);
        Ok(cmd)
    }
    pub fn scp_send_cmd(&self, files: &[String], dest: Option<&String>) -> Result<Command> {
        let mut cmd = Command::new("scp");
        cmd.args(self.gen_scp_send_args(files, dest)?);
        Ok(cmd)
    }

    pub fn ssh_cmd(&self, additional_ssh_args: Option<&[&str]>) -> Result<Command> {
        let mut cmd = Command::new("ssh");
        cmd.args(self.gen_ssh_args(additional_ssh_args)?);
        Ok(cmd)
    }
    pub fn ssh_cmd_async(
        &self,
        additional_ssh_args: Option<&[&str]>,
    ) -> Result<async_process::Command> {
        let mut cmd = async_process::Command::new("ssh");
        cmd.args(self.gen_ssh_args(additional_ssh_args)?);
        Ok(cmd)
    }
    /// run_cmd_piped will execute the given cmd on a remote machine.
    /// stdio will be pass-throughed to cro3's stdio.
    pub fn run_cmd_piped<T: AsRef<str> + AsRef<OsStr> + std::fmt::Debug>(
        &self,
        arg: &[T],
    ) -> Result<()> {
        let mut ssh = self.ssh_cmd(None)?;
        ssh.args(arg);
        let cmd = ssh.spawn()?;
        let result = cmd.wait_with_output()?;
        result.status.exit_ok().context(anyhow!(
            "run_cmd_piped failed with {:?}. cmd = {:?}",
            result.status.code(),
            arg
        ))
    }
    fn run_cmd_captured(&self, cmd: &str) -> Result<Output> {
        let mut ssh = self.ssh_cmd(None)?;
        ssh.arg(cmd).stdout(Stdio::piped()).stderr(Stdio::piped());
        let cmd = ssh.spawn()?;
        let output = cmd
            .wait_with_output()
            .context("wait_with_output failed in run_cmd_captured")?;
        if output.status.success() {
            Ok(output)
        } else {
            let stdout = get_stdout(&output);
            let stderr = get_stderr(&output);
            bail!("run_cmd_captured failed: {} {}", stdout, stderr)
        }
    }
    pub fn open_ssh(&self) -> Result<()> {
        let cmd = self.ssh_cmd(None)?.spawn()?;
        let exit_status = cmd.wait_with_output()?.status;
        // stdout and stderr is not captured so printing them here is useless
        exit_status.exit_ok().or(Err(anyhow!(
            "Failed to establish ssh connection. code = {:?}",
            exit_status.code()
        )))
    }

    pub fn start_port_forwarding(
        &self,
        port: u16,
        dut_port: u16,
        command: &str,
    ) -> Result<async_process::Child> {
        let child = self
            .ssh_cmd_async(Some(&[
                "-L",
                &format!("{}:127.0.0.1:{}", port, dut_port),
                "-o",
                "ExitOnForwardFailure yes",
                "-o",
                "ServerAliveInterval=5",
                "-o",
                "ServerAliveCountMax=1",
            ]))?
            .arg(command)
            .kill_on_drop(true)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()?;
        Ok(child)
    }
    // Start SSH port forwarding on a given port.
    // The future will be resolved once the first connection attempt is succeeded.
    pub async fn start_ssh_forwarding(&self, port: u16) -> Result<async_process::Child> {
        self.start_ssh_forwarding_in_range(port..=port)
        .await
        .map(|e| e.0)
    }
    // Start SSH port forwarding in a given range without timeout.
    pub async fn start_ssh_forwarding_in_range(
        &self,
        port_range: RangeInclusive<u16>,
    ) -> Result<(async_process::Child, u16)> {
        const COMMON_PORT_FORWARD_TOKEN: &str = "cro3-ssh-portforward";
        let sshcmd = &format!("echo {COMMON_PORT_FORWARD_TOKEN}; sleep 8h");
        let mut ports: Vec<u16> = port_range.into_iter().collect::<Vec<u16>>();
        let mut rng = thread_rng();
        ports.shuffle(&mut rng);
        for port in ports {
            // Try to establish port forwarding
            let mut child = self.start_port_forwarding(port, 22, sshcmd)?;
            let (ssh_stdout, ssh_stderr) = get_async_lines(&mut child);
            let ssh_stdout = ssh_stdout.context(anyhow!("ssh_stdout was None"))?;
            let ssh_stderr = ssh_stderr.context(anyhow!("ssh_stderr was None"))?;
            let mut merged_stream = stream::select(ssh_stdout.fuse(), ssh_stderr.fuse());
            loop {
                let mut merged_stream = merged_stream.next();
                select! {
                    line = merged_stream => {
                        if let Some(Ok(line)) = line {
                            if line.contains(COMMON_PORT_FORWARD_TOKEN) {
                                info!("cro3: Established SSH port forwarding for {self:?} on {port}");
                                return Ok((child, port));
                            }
                            info!("{line}");
                            if line.contains("cannot listen to port") {
                                // Try next port
                                break;
                            }
                        }
                    }
                    complete => {
                            // stdout is closed unexpectedly since ssh process is terminated.
                            // stderr may contain some info and will be closed as well,
                            // so do nothing here and wait for activities on stderr stream.
                        bail!("SSH process streams are closed");
                    }
                }
            }
        }

        bail!("Could not find a port available for forwarding")
    }
    /// Keep forwarding in background.
    /// The execution will be blocked until the first attemp succeeds, and the
    /// return value represents which port is used for this forwarding, or an
    /// error. Forwarding port on this side will be automatically determined by
    /// start_ssh_forwarding, and the same port will be used for reconnecting
    /// while this cro3 instance is running.
    fn start_ssh_forwarding_background_in_range(&self, port_range: RangeInclusive<u16>) -> Result<(u16, async_process::Child)> {
        let port_file = tempfile::NamedTempFile::new()?;
        let port_file_path = port_file.into_temp_path();
        let child = async_process::Command::new(current_exe()?)
            .args(&[
                "dut",
                "forward",
                "--dut",
                &self.host_and_port(),
                "--port-file",
                &port_file_path.as_os_str().to_string_lossy(),
                "--port-first",
                &format!("{}", port_range.start()),
                "--port-last",
                &format!("{}", port_range.end()),
            ])
            .kill_on_drop(false)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()?;
        let port = retry(retry::delay::Fixed::from_millis(1000).take(60), || -> Result<u16> {
            info!("setting up a port forwarding...");
            let port = std::fs::read_to_string(&port_file_path)?;
            let port: u16 = port.trim().parse()?;
            Result::Ok(port)
        }).or(Err(anyhow!("Failed to establish the port forwarding")))?;
        Ok((port, child))
    }
    pub fn start_ssh_forwarding_background(&self) -> Result<(u16, async_process::Child)> {
        self.start_ssh_forwarding_background_in_range(4100..=4200)
    }
    pub fn run_cmd_stdio(&self, cmd: &str) -> Result<String> {
        let output = self.run_cmd_captured(cmd)?;
        if output.status.success() {
            Ok(get_stdout(&output))
        } else {
            Err(anyhow!(
                "run_cmd_stdio failed: {} {}",
                get_stderr(&output),
                get_stdout(&output)
            ))
        }
    }
    pub fn run_autologin(&self) -> Result<()> {
        self.run_cmd_piped(&["/usr/local/autotest/bin/autologin.py", "-a", "-d"])
    }
    pub fn get_host_kernel_config(&self) -> Result<String> {
        self.run_cmd_stdio("modprobe configs; zcat /proc/config.gz")
    }
    pub fn get_board(&self) -> Result<String> {
        self.run_cmd_stdio("cat /etc/lsb-release | grep CHROMEOS_RELEASE_BOARD | cut -d '=' -f 2")
    }
    pub fn get_arch(&self) -> Result<String> {
        // Return "x86_64" or "arm64"
        self.run_cmd_stdio("uname -m | sed s/aarch64/arm64/")
    }
    pub fn get_rootdev(&self) -> Result<String> {
        self.run_cmd_stdio("rootdev -s")
    }
    pub fn get_rootdisk(&self) -> Result<String> {
        let rootdev = self.get_rootdev()?;
        Ok(rootdev
            .trim_end_matches(char::is_numeric)
            .trim_end_matches('p')
            .to_string())
    }
    pub fn get_partnum_info(&self) -> Result<HashMap<String, String>> {
        let cmd_str = "source /usr/sbin/write_gpt.sh; load_base_vars;
            echo kern_a=${PARTITION_NUM_KERN_A}; echo root_a=${PARTITION_NUM_ROOT_A};
            echo kern_b=${PARTITION_NUM_KERN_B}; echo root_b=${PARTITION_NUM_ROOT_B}";
        let res = self.run_cmd_stdio(cmd_str)?;
        let mut info = HashMap::new();
        for i in res.split_whitespace() {
            if let Some((key, value)) = i.split_once('=') {
                info.insert(key.to_string(), value.to_string());
            }
        }
        Ok(info)
    }
    pub fn get_arc_version(&self) -> Result<String> {
        self.run_cmd_stdio("cat /etc/lsb-release | grep CHROMEOS_ARC_VERSION= | cut -d '=' -f 2")
    }
    pub fn get_arc_device(&self) -> Result<String> {
        // Return "cheets" or "bertha"
        self.run_cmd_stdio("test -d /opt/google/vms/android && echo bertha || echo cheets")
    }
    pub fn get_uptime(&self) -> Result<Duration> {
        let uptime = self
            .run_cmd_stdio("cat /proc/uptime")
            .context("Failed to read /proc/uptime")?;
        let uptime = uptime
            .split(' ')
            .next()
            .ok_or(anyhow!("Failed to parse uptime"))?;
        Ok(Duration::from_secs_f64(f64::from_str(uptime)?))
    }
    pub fn get_arc_image_type(&self) -> Result<String> {
        let arc_dir = if self.get_arc_device()? == "cheets" {
            "arc"
        } else {
            "arcvm"
        };
        self.run_cmd_stdio(&format!(
            "grep ro.build.type /usr/share/{}/properties/build.prop | cut -d '=' -f 2",
            arc_dir
        ))
    }
    pub fn get_files(&self, files: &[String], dest: Option<&String>) -> Result<()> {
        let mut cmd = self.scp_get_cmd(files, dest)?;
        let chd = cmd.stderr(Stdio::piped()).spawn()?;
        let result = chd.wait_with_output()?;
        let stderr = get_stderr(&result);
        result.status.exit_ok().context(anyhow!(
            r#"Failed to run scp {cmd:?}:
stderr:
    {}"#,
            stderr
        ))
    }
    pub fn send_files(&self, files: &[String], dest: Option<&String>) -> Result<()> {
        let mut cmd = self.scp_send_cmd(files, dest)?;
        let chd = cmd.stderr(Stdio::piped()).spawn()?;
        let result = chd.wait_with_output()?;
        let stderr = get_stderr(&result);
        result.status.exit_ok().context(anyhow!(
            "Failed to run scp {cmd:?}:\nstderr:\n    {}",
            stderr
        ))
    }
    pub fn switch_partition_set(&self, target: PartitionSet) -> Result<()> {
        let rootdev = self.get_rootdev()?;
        let rootdisk = self.get_rootdisk()?;
        let part = self.get_partnum_info()?;
        let kern_a = part.get("kern_a").ok_or(anyhow!("KERN-A not found"))?;
        let kern_b = part.get("kern_b").ok_or(anyhow!("KERN-B not found"))?;
        let root_a = part.get("root_a").ok_or(anyhow!("ROOT-A not found"))?;
        let root_b = part.get("root_b").ok_or(anyhow!("ROOT-B not found"))?;
        let (current_name, current_kern, current_root, other_name, other_kern, other_root) =
            if rootdev.ends_with(root_a) {
                ("A", kern_a, root_a, "B", kern_b, root_b)
            } else if rootdev.ends_with(root_b) {
                ("B", kern_b, root_b, "A", kern_a, root_a)
            } else {
                bail!("unsupported partition layout");
            };
        let cmd = match target {
            PartitionSet::Primary => {
                println!("switching to primary: {current_name} ({rootdisk}p{current_root})");
                format!("cgpt prioritize -P2 -i {current_kern} {rootdisk}")
            }
            PartitionSet::Secondary => {
                println!("switching to secondary: {other_name} ({rootdisk}p{other_root})");
                format!("cgpt prioritize -P2 -i {other_kern} {rootdisk}")
            }
        };
        self.run_cmd_piped(&[cmd])
    }
    pub fn reboot(&self) -> Result<()> {
        self.run_cmd_piped(&["reboot; exit"])
    }
    pub fn wait_online(&self) -> Result<()> {
        retry(retry::delay::Fixed::from_millis(1000), || {
            self.run_cmd_piped(&["echo ok"])
        })
        .or(Err(anyhow!("Timed out while waiting for DUT to be online")))
    }
}

/// KeyInfo holds values that can identify a physical DUT uniquely
#[derive(Clone, Debug)]
pub struct KeyInfo {
    key: String,
    model: String,
    serial: String,
}
impl KeyInfo {
    pub async fn from_raw_dut_info(info: &HashMap<String, String>) -> Result<Self> {
        let model = info.get("model").context("failed to get model")?.clone();
        let serial = info.get("serial").context("failed to get serial")?.clone();
        let key = model.clone() + "_" + &serial;
        Ok(Self { key, model, serial })
    }
    pub fn key(&self) -> &str {
        &self.key
    }
    pub fn model(&self) -> &str {
        &self.model
    }
    pub fn serial(&self) -> &str {
        &self.serial
    }
}

pub fn pingable_duts() -> Result<Vec<SshInfo>> {
    Ok(SSH_CACHE
        .entries()
        .context(anyhow!("SSH_CACHE is not initialized yet"))?
        .iter()
        .flat_map(|it| {
            let ssh = it.1;
            ssh.ping().and(Ok(ssh.clone()))
        })
        .collect())
}

pub fn fetch_dut_info_in_parallel(
    addrs: &Vec<String>,
    extra_attr: &[String],
) -> Result<Vec<DutInfo>> {
    rayon::ThreadPoolBuilder::new()
        .num_threads(std::cmp::min(16, addrs.len()))
        .build_global()
        .context("Failed to set thread count")?;
    Ok(addrs
        .par_iter()
        .flat_map(|addr| -> Result<DutInfo> {
            let addr = &format!("[{}]", addr);
            // Since we are listing the DUTs on the same network
            // so assume that port 22 is open for ssh
            let ssh = SshInfo::new_host_and_port(addr, 22).context("failed to create SshInfo")?;
            let dut = block_on(DutInfo::from_ssh(&ssh, extra_attr));
            match &dut {
                Ok(_) => {
                    info!("{} is a DUT :)", addr)
                }
                Err(e) => {
                    info!("{} is not a DUT...(ToT) : {:#}", addr, e)
                }
            }
            dut
        })
        .collect())
}

pub fn discover_local_nodes(iface: Option<String>) -> Result<Vec<String>> {
    ensure_testing_rsa_is_there()?;
    info!("Detecting DUTs on the same network...");
    let iface = iface
        .ok_or(())
        .or_else(|_| -> Result<String, anyhow::Error> {
            let r = run_bash_command(CMD_GET_DEFAULT_IFACE, None)
                .context("failed to determine interface to scan from ip route")?;
            r.status.exit_ok()?;
            Ok(get_stdout(&r).trim().to_string())
        })
        .context("Failed to determine interface to scan")?;
    info!("Using {iface} to scan...");
    let output = run_bash_command(
        &format!(
            "ping6 -c 3 -I {iface} ff02::1 | grep 'bytes from' | cut -d ' ' -f 4 | tr -d ',' | \
             sort | uniq"
        ),
        None,
    )?;
    let stdout = get_stdout(&output);
    let addrs = stdout
        .split('\n')
        .map(str::to_string)
        .collect::<Vec<String>>();
    Ok(addrs)
}

pub fn register_dut(dut: &str) -> Result<DutInfo> {
    info!("Checking DutInfo of {dut:?}...");
    let info = DutInfo::new(dut)?;
    let id = info.id();
    let ssh = info.ssh();
    SSH_CACHE.set(id, ssh.clone())?;
    info!("Added: {:32} {}", id, serde_json::to_string(ssh)?);
    Ok(info)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn regex() {
        // bracketed ipv6 address is prohibited as an internal representation
        assert!(!RE_DUT_HOST_NAME.is_match("[fe00::]"));
        // but allowed for inputs
        assert!(RE_IPV6_WITH_BRACKETS.is_match("[fe00::]"));
        assert_eq!(
            &RE_IPV6_WITH_BRACKETS.captures("[fe00::]").unwrap()["addr"],
            "fe00::"
        );
        // %ifname should be supported for IPv6 link local addresses
        assert_eq!(
            &RE_IPV6_WITH_BRACKETS.captures("[fe00::%eth0]").unwrap()["addr"],
            "fe00::%eth0"
        );
        assert!(!RE_IPV6_WITH_BRACKETS.is_match("fe00::]"));
        assert!(!RE_IPV6_WITH_BRACKETS.is_match("[fe00::"));

        assert!(RE_DUT_HOST_NAME.is_match("1.2.3.4"));
        assert!(!RE_DUT_HOST_NAME.is_match(" 1.2.3.4"));

        assert!(RE_DUT_HOST_NAME.is_match("fe00::"));
        assert!(RE_DUT_HOST_NAME.is_match("fe00::"));
        // %ifname should be supported for IPv6 link local addresses
        assert!(RE_DUT_HOST_NAME.is_match("fe00::%eth0"));
        assert!(RE_DUT_HOST_NAME.is_match("a:"));
        assert!(!RE_DUT_HOST_NAME.is_match("fe00:: "));
        assert!(!RE_DUT_HOST_NAME.is_match(" fe00::"));

        assert!(RE_DUT_HOST_NAME.is_match("chromium.org"));
        assert!(RE_DUT_HOST_NAME.is_match("a"));
        assert!(!RE_DUT_HOST_NAME.is_match(" chromium.org "));
        assert!(!RE_DUT_HOST_NAME.is_match(""));
        assert!(!RE_DUT_HOST_NAME.is_match(" "));
        assert!(!RE_DUT_HOST_NAME.is_match("a\t"));
        assert!(!RE_DUT_HOST_NAME.is_match("a\n"));
        assert!(!RE_DUT_HOST_NAME.is_match("a\r"));
        assert!(!RE_DUT_HOST_NAME.is_match("a "));
        assert!(!RE_DUT_HOST_NAME.is_match("a#"));
        assert!(!RE_DUT_HOST_NAME.is_match("a/"));
        assert!(!RE_DUT_HOST_NAME.is_match("g:"));
        assert!(!RE_DUT_HOST_NAME.is_match("g<"));
        assert!(!RE_DUT_HOST_NAME.is_match("g>"));
        assert!(!RE_DUT_HOST_NAME.is_match("a?"));
        assert!(!RE_DUT_HOST_NAME.is_match("a@"));
        assert!(!RE_DUT_HOST_NAME.is_match("a["));
        assert!(!RE_DUT_HOST_NAME.is_match("a]"));
        assert!(!RE_DUT_HOST_NAME.is_match("a^"));
        assert!(!RE_DUT_HOST_NAME.is_match("a|"));

        assert!(RE_GBB_FLAGS.is_match("0x00000000"));
        assert!(RE_GBB_FLAGS.is_match("0x00000019"));
        assert!(!RE_GBB_FLAGS.is_match("0x00000019 "));
        assert!(!RE_GBB_FLAGS.is_match(" 0x00000019"));
        assert!(!RE_GBB_FLAGS.is_match("flags: 0x00000019"));
    }

    #[test]
    fn info_dut_id_failure() {
        let keys = vec!["dut_id"];
        let values = HashMap::new();
        let result_actual = DutInfo::parse_values(&keys, values);
        assert!(result_actual.is_err());
    }
    #[test]
    fn info_dut_id() {
        let keys = vec!["dut_id"];
        let mut values = HashMap::new();
        values.insert("model".to_string(), Ok("MODEL".to_string()));
        values.insert("serial".to_string(), Ok("SERIAL".to_string()));
        let result_actual = DutInfo::parse_values(&keys, values);
        let mut result_expected = HashMap::new();
        result_expected.insert("dut_id".to_string(), "MODEL_SERIAL".to_string());
        let result_expected: HashMap<String, String> = result_expected;
        assert_eq!(result_actual.expect("result should be Ok"), result_expected);
    }
    #[test]
    fn default_dut_info_has_no_env_specific_keys() {
        assert!(!DEFAULT_DUT_INFO_KEYS
            .iter()
            .any(|&k| { k == "ipv6_addr" || k == "ipv4_addr" }));
    }
}
