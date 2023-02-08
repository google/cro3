// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use crate::cache::KvCache;
use crate::config::Config;
use crate::cros::ensure_testing_rsa_is_there;
use crate::parser::LsbRelease;
use crate::util::get_async_lines;
use crate::util::get_stderr;
use crate::util::get_stdout;
use crate::util::run_bash_command;
use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use base64::engine::general_purpose::STANDARD;
use base64::Engine;
use chrono::Local;
use futures::executor::block_on;
use futures::select;
use futures::FutureExt;
use futures::StreamExt;
use lazy_static::lazy_static;
use rand::seq::SliceRandom;
use rand::thread_rng;
use rayon::prelude::*;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::ffi::OsStr;
use std::process::Command;
use std::process::Output;
use std::process::Stdio;
use std::str::FromStr;
use std::time::Duration;
use url::Url;

const COMMON_SSH_OPTIONS: [&str; 14] = [
    // Do not read ~/.ssh/config
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
    // Silence the messages
    "-o",
    "LogLevel=QUIET",
    // Connection timeout
    "-o",
    "ConnectTimeout=10",
];
const COMMON_PORT_FORWARD_TOKEN: &str = "lium-ssh-portforward";

lazy_static! {
    static ref RE_IPV6_WITH_BRACKETS: Regex = Regex::new(r"^\[(?P<addr>[0-9a-fA-F:]+(%.*)?)\]$").unwrap();
    // based on https://url.spec.whatwg.org/#host-miscellaneous
    static ref RE_DUT_HOST_NAME: Regex =
        Regex::new(r"^(([0-9.]+)|([0-9a-fA-F:]+(%.*)?)|([^\t\n\r #/:<>?@\[\]^|]+))$").unwrap();
}

#[test]
fn regex_test() {
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
}

pub static SSH_CACHE: KvCache<SshInfo> = KvCache::new("ssh_cache");

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
            child: ssh.start_ssh_forwarding(port).ok(),
            reconnecting: false,
        };
        Ok(dut)
    }
    pub fn reconnecting(&self) -> bool {
        self.reconnecting
    }
    fn reconnect(&mut self) -> Result<String> {
        let new_child = self.ssh.start_ssh_forwarding(self.port);
        if let Err(e) = &new_child {
            eprintln!("Failed to reconnect: {e:?}");
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

/// DutInfo holds information around a DUT
#[derive(Debug, Clone)]
pub struct DutInfo {
    key: KeyInfo,
    ssh: SshInfo,
    info: HashMap<String, String>,
}
impl DutInfo {
    async fn from_ssh(ssh: &SshInfo) -> Result<Self> {
        let info = Self::fetch_keys(
            ssh,
            &vec![
                "timestamp",
                "dut_id",
                "hwid",
                "address",
                "release",
                "model",
                "serial",
                "mac",
                "board",
                "ipv6_addrs",
            ],
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
    pub fn new(dut: &str) -> Result<Self> {
        let ssh = SshInfo::new(dut).context("failed to create SshInfo")?;
        block_on(Self::from_ssh(&ssh))
    }
    pub fn new_host_and_port(host: &str, port: u16) -> Result<Self> {
        let ssh = SshInfo::new_host_and_port(host, port).context("failed to create SshInfo")?;
        block_on(Self::from_ssh(&ssh))
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
    fn fetch_keys(ssh: &SshInfo, keys: &Vec<&str>) -> Result<HashMap<String, String>> {
        ensure_testing_rsa_is_there()?;
        eprintln!("Fetching info for {:?}...", ssh);
        let base_result = ssh
            .run_cmd_stdio(
                &[
                    r"echo board `cat /etc/lsb-release | grep CHROMEOS_RELEASE_BOARD | cut -d '=' -f 2 | cut -d '-' -f 1 | base64 -w 0`",
                r"echo hwid `crossystem hwid | base64 -w 0`",
                    r"echo arch `crossystem arch | base64 -w 0`",
                    r"echo serial `vpd -g serial_number | base64 -w 0`",
                    r"echo model_from_cros_config `cros_config / name ||  | base64 -w 0`",
                    r"echo model_from_mosys `cros_config / name | base64 -w 0`",
                    r"echo ectool_temps_all `ectool temps all | base64 -w 0`",
                    r"echo get_gbb_flags `/usr/share/vboot/bin/get_gbb_flags.sh 2>&1 | base64 -w 0`",
                    //"echo host_kernel_config `modprobe configs; zcat /proc/config.gz | base64 -w 0`",
                    r"echo lshw `lshw -json | base64 -w 0`",
                    r"echo lsb_release `cat /etc/lsb-release | base64 -w 0`",
                    r"echo ipv6_addr `ip -6 address show dev eth0 mngtmpaddr | grep inet6 | sed -E 's/\s+/ /g' | tr '/' ' ' | cut -d ' ' -f 3 | base64 -w 0`",
                    r"echo ipv6_addrs `ip -6 address show dev eth0 mngtmpaddr | grep inet6 | sed -E 's/\s+/ /g' | tr '/' ' ' | cut -d ' ' -f 3 | base64 -w 0`",
                    r"echo mac `ip addr show dev eth0 | grep ether | grep -E -o '([0-9a-z]{2}:){5}([0-9a-z]{2})' | head -n 1 | base64 -w 0`",
                    r"echo release `cat /etc/lsb-release | grep CHROMEOS_RELEASE_DESCRIPTION | sed -e 's/CHROMEOS_RELEASE_DESCRIPTION=//' | base64 -w 0`",
                ]
                .join(" ; "),
            )?;
        let mut base_result: HashMap<String, String> = base_result
            .split('\n')
            .flat_map(|s| {
                let s = s.split(' ').collect::<Vec<&str>>();
                if s.len() == 2 {
                    Ok((
                        s[0].to_string(),
                        String::from_utf8(STANDARD.decode(s[1])?)?
                            .trim()
                            .to_string(),
                    ))
                } else {
                    Err(anyhow!("Not a valid row"))
                }
            })
            .collect();
        if let Some(model) = base_result.get("model_from_cros_config") {
            base_result.insert("model".to_string(), model.clone());
        } else if let Some(model) = base_result.get("model_from_mosys") {
            base_result.insert("model".to_string(), model.clone());
        }
        let model = base_result.get("model").context("model was empty")?.clone();
        let serial = base_result
            .get("serial")
            .context("serial was empty")?
            .clone();
        let dut_id = format!("{model}_{serial}");
        base_result.insert("dut_id".to_string(), dut_id.clone());
        base_result.insert("timestamp".to_string(), Local::now().to_string());

        let mut values: HashMap<String, String> = HashMap::new();
        let target = if let Some(lab_ip) = base_result.get("ipv6_addr") {
            // Lab DUT
            SshInfo::new_host_and_port(lab_ip, 22)?
        } else {
            // Local DUT
            ssh.clone()
        };
        SSH_CACHE.set(&dut_id, target.clone())?;
        for key in keys {
            let value = if let Some(value) = base_result.get(*key) {
                value.clone()
            } else {
                match *key {
                "address" => Ok(target.host_and_port()),
                "dev_boot_usb" =>
                    Ok(target.run_cmd_stdio("crossystem dev_boot_usb")?.to_string()),
                "dev_default_boot" =>
                    Ok(target.run_cmd_stdio("crossystem dev_default_boot")?.to_string()),
                "dut_id" => continue,
                "ectool_temps_all" =>
                    Ok(target.run_cmd_stdio("ectool temps all")?.to_string()),
                "fwid" => {
                    let fwid = target.run_cmd_stdio("crossystem fwid")?;
                    Ok(fwid.to_string())
                }
                "gbb_flags" => {
                    let gbb_flags = target.run_cmd_stdio("/usr/share/vboot/bin/get_gbb_flags.sh 2>&1 | grep 'Chrome OS GBB set flags' | cut -d ':' -f 2",
                        )?;
                    Ok(gbb_flags.to_string())
                }
                "host_kernel_config" =>
                    Ok(target.run_cmd_stdio("modprobe configs; zcat /proc/config.gz")?.to_string()),
                "lshw" =>
                    Ok(target.run_cmd_stdio("lshw -json")?.to_string()),
                "mac" => Ok(target.get_mac_addr()?),
                "model" => Ok(model.clone()),
                "release" => {
                    Ok(target.run_cmd_stdio("cat /etc/lsb-release | grep CHROMEOS_RELEASE_DESCRIPTION | sed -e 's/CHROMEOS_RELEASE_DESCRIPTION=//'")?.to_string())
                }
                "ro_fwid" =>
                    Ok(target.run_cmd_stdio("crossystem ro_fwid")?.to_string()),
                "serial" => Ok(serial.clone()),
                "timestamp" => continue,
                "uptime" => Ok(target.get_uptime()?.as_secs_f64().to_string()),
                key => Err(anyhow!("unknown key: {}", key)),
            }?
            };
            values.insert(key.to_string(), value);
        }
        Ok(values)
    }
}

/// This test requires a working DUT so excluded by default
#[ignore]
#[test]
fn dut_info_is_valid() {
    let ip = std::env::var("DUT")
        .context("please set DUT env var correctly")
        .unwrap();
    eprintln!("Using DUT = {ip}");
    let ssh = SshInfo::new(&ip).expect("Failed to create ssh info");
    let keys = vec!["dut_id", "hwid", "address", "model", "serial", "mac"];
    let info = DutInfo::fetch_keys(&ssh, &keys).expect("Failed to fetch DUT info");
    assert_eq!(
        info.get("serial").map(String::as_str),
        Some("NXHTZSJ00403428C037600")
    );
    assert_eq!(
        info.get("hwid").map(String::as_str),
        Some("KLED-QYGU C5I-A2B-E5P-74H-A3O")
    );
    assert_eq!(
        info.get("dut_id").map(String::as_str),
        Some("kled_NXHTZSJ00403428C037600")
    );
    assert_eq!(info.get("address").map(String::as_str), Some(ip.as_str()));
    assert_eq!(
        info.get("mac").map(String::as_str),
        Some("48:65:ee:15:07:9c")
    );
    assert_eq!(info.get("model").map(String::as_str), Some("kled"));
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
    /// stdio will be pass-throughed to lium's stdio.
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
            Err(anyhow!("run_cmd_captured failed: {} {}", stdout, stderr))
        }
    }
    pub fn open_ssh(&self) -> Result<()> {
        let cmd = self.ssh_cmd(None)?.spawn()?;
        let result = cmd.wait_with_output()?;
        let stdout = get_stdout(&result);
        let stderr = get_stderr(&result);
        result.status.exit_ok().context(anyhow!(
            "Failed to establish ssh connection:\nstdout:\n{}\nstderr:\n{}",
            stdout,
            stderr
        ))
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
    pub fn start_ssh_forwarding(&self, port: u16) -> Result<async_process::Child> {
        self.start_port_forwarding(port, 22, "sleep 8h")
    }
    // Start SSH port forwarding in given range
    pub fn start_ssh_forwarding_range(
        &self,
        port_range: (u16, u16),
    ) -> Result<(async_process::Child, u16)> {
        let sshcmd = &format!("echo {COMMON_PORT_FORWARD_TOKEN}; sleep 8h");
        block_on(async {
            let mut ports = (port_range.0..port_range.1)
                .into_iter()
                .collect::<Vec<u16>>();
            let mut rng = thread_rng();
            ports.shuffle(&mut rng);
            for port in ports {
                // Try to establish port forwarding
                let mut child = self.start_port_forwarding(port, 22, sshcmd)?;
                let (mut ssh_stdout, mut ssh_stderr) = get_async_lines(&mut child);
                loop {
                    let mut ssh_stdout = ssh_stdout.next().fuse();
                    let mut ssh_stderr = ssh_stderr.next().fuse();
                    select! {
                        line = ssh_stderr => {
                            if let Some(line) = line {
                                let line = line?;
                                if line.contains("cannot listen to port") {
                                    break;
                                }
                            } else {
                                return Err(anyhow!("ssh failed unexpectedly"));
                            }
                        }
                        line = ssh_stdout => {
                            if let Some(line) = line {
                                let line = line?;
                                if line.contains(COMMON_PORT_FORWARD_TOKEN) {
                                    return Ok((child, port));
                                }
                            } else {
                                return Err(anyhow!("ssh failed unexpectedly"));
                            }
                        }
                    }
                }
            }
            return Err(anyhow!("Do not find any vacant port"));
        })
    }
    pub fn run_cmd_stdio(&self, cmd: &str) -> Result<String> {
        let output = self.run_cmd_captured(cmd)?;
        if output.status.success() {
            Ok(crate::util::get_stdout(&output))
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
    pub fn get_lsb_release(&self) -> Result<LsbRelease> {
        let lsb_release = self
            .run_cmd_stdio("cat /etc/lsb-release")
            .context("Failed to read /etc/lsb-release")?;
        LsbRelease::from_str(&lsb_release).context("Failed to parse /etc/lsb_release")
    }
    pub fn get_host_kernel_config(&self) -> Result<String> {
        self.run_cmd_stdio("modprobe configs; zcat /proc/config.gz")
    }
    pub fn get_board(&self) -> Result<String> {
        self.run_cmd_stdio("cat /etc/lsb-release | grep CHROMEOS_RELEASE_BOARD | cut -d '=' -f 2")
    }
    pub fn get_ipv6_addr(&self) -> Result<String> {
        self
                .run_cmd_stdio(r"ip -6 address show dev eth0 mngtmpaddr | grep inet6 | grep 2401:fa00:480:ee08 | sed -E 's/\s+/ /g' | tr '/' ' ' | cut -d ' ' -f 3")
    }
    pub fn get_mac_addr(&self) -> Result<String> {
        self
                .run_cmd_stdio(r"ip addr show dev eth0 | grep ether | grep -E -o '([0-9a-z]{2}:){5}([0-9a-z]{2})' | head -n 1")
    }
    pub fn get_serial(&self) -> Result<String> {
        self.run_cmd_stdio("vpd -g serial_number")
    }
    pub fn get_arch(&self) -> Result<String> {
        // Return "x86_64" or "arm64"
        self.run_cmd_stdio("uname -m | sed s/aarch64/arm64/")
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
        let chd = cmd.spawn()?;
        let result = chd.wait_with_output()?;
        let stdout = get_stdout(&result);
        let stderr = get_stderr(&result);
        result.status.exit_ok().context(anyhow!(
            "Failed to run scp {cmd:?}:\nstdout:\n{}\nstderr:\n{}",
            stdout,
            stderr
        ))
    }
    pub fn send_files(&self, files: &[String], dest: Option<&String>) -> Result<()> {
        let mut cmd = self.scp_send_cmd(files, dest)?;
        let chd = cmd.spawn()?;
        let result = chd.wait_with_output()?;
        let stdout = get_stdout(&result);
        let stderr = get_stderr(&result);
        result.status.exit_ok().context(anyhow!(
            "Failed to run scp {cmd:?}:\nstdout:\n{}\nstderr:\n{}",
            stdout,
            stderr
        ))
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

pub fn discover_local_duts(iface: Option<String>) -> Result<Vec<DutInfo>> {
    ensure_testing_rsa_is_there()?;
    eprintln!("Detecting DUTs on the same network...");
    let iface = iface
        .ok_or(())
        .or_else(|_| -> Result<String, anyhow::Error> {
            let r = run_bash_command("ip --json route | jq -r '.[0].dev'", None)
                .context("failed to determine interface to scan from ip route")?;
            r.status.exit_ok()?;
            Ok(get_stdout(&r).trim().to_string())
        })
        .context("Failed to determine interface to scan")?;
    eprintln!("Using {iface} to scan...");
    let output = run_bash_command(&format!(
        "ping6 -c 3 -I {iface} ff02::1 | grep 'bytes from' | cut -d ' ' -f 4 | tr -d ',' | sort | uniq"),
        None,
    )?;
    let stdout = get_stdout(&output);
    let addrs = stdout.split('\n').collect::<Vec<&str>>();
    eprintln!("Found {} candidates. Checking...", addrs.len());
    rayon::ThreadPoolBuilder::new()
        .num_threads(16)
        .build_global()
        .context("Failed to set thread count")?;
    let duts: Vec<DutInfo> = block_on(async {
        addrs
            .par_iter()
            .flat_map(|addr| -> Result<DutInfo> {
                let addr = &format!("[{}]", addr);
                let dut = DutInfo::new_host_and_port(addr, 22);
                match &dut {
                    Ok(_) => {
                        eprintln!("{} is a DUT :)", addr)
                    }
                    Err(e) => {
                        eprintln!("{} is not a DUT...(ToT) : {:#}", addr, e)
                    }
                }
                dut
            })
            .collect()
    });
    eprintln!("Discovery completed with {} DUTs", duts.len());
    Ok(duts)
}
