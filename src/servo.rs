// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use crate::chroot::Chroot;
use crate::config::Config;
use crate::util::get_async_lines;
use crate::util::get_stderr;
use crate::util::get_stdout;
use crate::util::has_root_privilege;
use crate::util::run_bash_command;
use crate::util::run_lium_with_sudo;
use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use async_process::Child;
use core::str::FromStr;
use futures::executor::block_on;
use futures::select;
use futures::FutureExt;
use futures::StreamExt;
use lazy_static::lazy_static;
use macaddr::MacAddr6;
use macaddr::MacAddr8;
use rand::seq::SliceRandom;
use rand::thread_rng;
use regex::Regex;
use retry::delay;
use retry::retry;
use serde::Deserialize;
use serde::Serialize;
use std::collections::BTreeMap;
use std::collections::HashSet;
use std::fmt;
use std::fmt::Display;
use std::fmt::Formatter;
use std::fs;
use std::iter::FromIterator;
use std::path::Path;
use std::time::Duration;

lazy_static! {
    static ref RE_MAC_ADDR: Regex =
        Regex::new(r"(?P<addr>([0-9A-Za-z]{2}:){5}([0-9A-Za-z]{2}))").unwrap();
    static ref RE_EC_VERSION: Regex = Regex::new(r"RO:\s*(?P<version>.*)\n").unwrap();
    static ref RE_GBB_FLAGS: Regex = Regex::new(r"^flags: 0x(?P<flags>[0-9a-fA-F]+)$").unwrap();
    static ref RE_USB_SYSFS_PATH_FUNC: Regex = Regex::new(r"\.[0-9]+$").unwrap();
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn regex() {
        assert!(RE_MAC_ADDR.is_match("FF:FF:FF:FF:FF:FF"));
        assert!(RE_MAC_ADDR.is_match("00:00:00:00:00:00"));
        assert!(RE_MAC_ADDR.is_match("99:99:99:99:99:99"));
        assert_eq!(
            &RE_MAC_ADDR
                .captures("Mac addr ff:ff:ff:ff:ff:ff should match")
                .unwrap()["addr"],
            "ff:ff:ff:ff:ff:ff"
        );
        assert_eq!(
            &RE_GBB_FLAGS.captures("flags: 0x000040b9").unwrap()["flags"],
            "000040b9"
        );
    }
}

fn get_usb_sysfs_path_stem(path: &str) -> String {
    RE_USB_SYSFS_PATH_FUNC.replace(path, "").to_string()
}

pub fn get_servo_attached_to_cr50(cr50: &LocalServo) -> Result<LocalServo> {
    let usb_path = cr50.usb_sysfs_path();
    let common_path = get_usb_sysfs_path_stem(usb_path);
    let list = discover()?;
    list.iter()
        .filter(|s| s.is_servo())
        .find(|s| get_usb_sysfs_path_stem(s.usb_sysfs_path()) == common_path)
        .cloned()
        .context(anyhow!("No Cr50 attached with the Servo found"))
}
pub fn get_cr50_attached_to_servo(servo: &LocalServo) -> Result<LocalServo> {
    let usb_path = servo.usb_sysfs_path();
    let common_path = get_usb_sysfs_path_stem(usb_path);
    let list = discover()?;
    list.iter()
        .filter(|s| s.is_cr50())
        .find(|s| get_usb_sysfs_path_stem(s.usb_sysfs_path()) == common_path)
        .cloned()
        .context(anyhow!("No Cr50 attached with the Servo found"))
}

fn read_usb_attribute(dir: &Path, name: &str) -> Result<String> {
    let value = dir.join(name);
    let value = fs::read_to_string(value)?;
    Ok(value.trim().to_string())
}

// This is private since users should use ServoList instead
fn discover() -> Result<Vec<LocalServo>> {
    let paths = fs::read_dir("/sys/bus/usb/devices/").unwrap();
    Ok(paths
        .flat_map(|usb_path| -> Result<LocalServo> {
            let usb_sysfs_path = usb_path?.path();
            let product = read_usb_attribute(&usb_sysfs_path, "product")?;
            let serial = read_usb_attribute(&usb_sysfs_path, "serial")?;
            if product.starts_with("Servo")
                || product.starts_with("Cr50")
                || product.starts_with("Ti50")
            {
                let paths = fs::read_dir(&usb_sysfs_path).context("failed to read dir")?;
                let tty_list: BTreeMap<String, String> = paths
                    .flat_map(|path| -> Result<(String, String)> {
                        let path = path?.path();
                        let interface = fs::read_to_string(path.join("interface"))?
                            .trim()
                            .to_string();
                        let tty_name = fs::read_dir(path)?
                            .find_map(|p| {
                                let s = p.ok()?.path();
                                let s = s.file_name()?.to_string_lossy().to_string();
                                s.starts_with("ttyUSB").then_some("/dev/".to_string() + &s)
                            })
                            .context("ttyUSB not found")?;
                        Ok((interface, tty_name))
                    })
                    .collect();
                Ok(LocalServo {
                    product,
                    serial,
                    usb_sysfs_path: usb_sysfs_path.to_string_lossy().to_string(),
                    tty_list,
                    ..Default::default()
                })
            } else {
                Err(anyhow!("Not a servo"))
            }
        })
        .collect())
}

fn discover_slow() -> Result<Vec<LocalServo>> {
    let mut servos = discover()?;
    servos.iter_mut().for_each(|s| {
        eprintln!("Checking {}", s.serial);
        let mac_addr = s.read_mac_addr().ok();
        let ec_version = s.read_ec_version().ok();
        s.cached_info = Some(CachedServoInfo {
            mac_addr,
            ec_version,
        })
    });
    Ok(servos)
}

pub fn reset_devices(serials: &Vec<String>) -> Result<()> {
    let servo_info = discover()?;
    let servo_info: Vec<LocalServo> = if !serials.is_empty() {
        let serials: HashSet<_> = HashSet::from_iter(serials.iter());
        servo_info
            .iter()
            .filter(|s| serials.contains(&s.serial().to_string()))
            .cloned()
            .collect()
    } else {
        servo_info
    };
    for s in &servo_info {
        s.reset()?;
    }
    std::thread::sleep(Duration::from_millis(1000));

    Ok(())
}

#[derive(Debug, Clone, Default, Serialize)]
pub struct ServoList {
    devices: Vec<LocalServo>,
}
impl ServoList {
    pub fn discover() -> Result<Self> {
        Ok(Self {
            devices: discover()?,
        })
    }
    pub fn discover_slow() -> Result<Self> {
        Ok(Self {
            devices: discover_slow()?,
        })
    }
    pub fn find_by_serial(&self, serial: &str) -> Result<&LocalServo> {
        self.devices
            .iter()
            .find(|s| s.serial() == serial)
            .context("Servo not found with a given serial")
    }
    pub fn devices(&self) -> &Vec<LocalServo> {
        &self.devices
    }
}
impl Display for ServoList {
    fn fmt(&self, f: &mut Formatter) -> fmt::Result {
        write!(
            f,
            "{}",
            serde_json::to_string_pretty(&self).map_err(|_| fmt::Error)?
        )
    }
}

#[derive(Debug, Clone, Deserialize, Serialize, Default)]
pub struct CachedServoInfo {
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    mac_addr: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(default)]
    ec_version: Option<String>,
}
impl CachedServoInfo {}

#[derive(Debug, Clone, Deserialize, Serialize, Default)]
pub struct LocalServo {
    product: String,
    serial: String,
    usb_sysfs_path: String,
    // Using BTreeMap here to keep the ordering when printing this structure
    tty_list: BTreeMap<String, String>,
    cached_info: Option<CachedServoInfo>,
}
impl LocalServo {
    pub fn product(&self) -> &str {
        &self.product
    }
    pub fn serial(&self) -> &str {
        &self.serial
    }
    pub fn tty_list(&self) -> &BTreeMap<String, String> {
        &self.tty_list
    }
    pub fn tty_path(&self, tty_type: &str) -> Result<String> {
        let path = self
            .tty_list()
            .get(tty_type)
            .context(anyhow!("tty[{}] not found", tty_type))?;
        Ok(path.clone())
    }
    pub fn run_cmd(&self, tty_type: &str, cmd: &str) -> Result<String> {
        let tty_path = self.tty_path(tty_type)?;
        // Check if socat is installed
        let socat_path = run_bash_command("which socat", None)?;
        let socat_path = get_stdout(&socat_path);
        if socat_path.trim().is_empty() {
            return Err(anyhow!("socat not found. Please install socat with something like: `sudo apt install socat`"));
        }
        // stat tty_path first to ensure that the tty is available
        let output = run_bash_command(
            &format!("stat {tty_path} && echo {cmd} | socat - {tty_path},echo=0,crtscts=1"),
            None,
        )?;
        output
            .status
            .exit_ok()
            .context(anyhow!("servo command failed: {}", get_stderr(&output)))?;
        Ok(get_stdout(&output))
    }
    pub fn usb_sysfs_path(&self) -> &str {
        &self.usb_sysfs_path
    }
    pub fn reset(&self) -> Result<()> {
        if has_root_privilege()? {
            eprintln!("Resetting servo device: {}", self.serial);
            let path = Path::new(&self.usb_sysfs_path).join("authorized");
            fs::write(&path, b"0").context(anyhow!("Failed to set authorized = 0 {path:?}"))?;
            if let Err(e) = fs::write(&path, b"1") {
                // sometimes writing to `authorized` fails with EPIPE, but it can be ignored.
                eprintln!("Warning: Failed to set authorized = 1 {path:?} ({e:?})");
            }
            Ok(())
        } else {
            run_lium_with_sudo(&["servo", "reset", self.serial()])
        }
    }
    pub fn from_serial(serial: &str) -> Result<LocalServo> {
        let servos = discover()?;
        Ok(servos
            .iter()
            .find(|&s| s.serial == serial)
            .context(anyhow!("Servo not found: {serial}"))?
            .clone())
    }
    fn start_servod_on_port(&self, chroot: &Chroot, port: u16) -> Result<Child> {
        chroot
            .exec_in_chroot_async(&[
                "sudo",
                "servod",
                "-s",
                &self.serial,
                "-p",
                &port.to_string(),
            ])
            .context("failed to launch servod")
    }
    pub fn start_servod(&self, chroot: &Chroot) -> Result<ServodConnection> {
        block_on(async {
            eprintln!("Starting servod...");
            let mut ports = (9000..9099).into_iter().collect::<Vec<u16>>();
            let mut rng = thread_rng();
            ports.shuffle(&mut rng);
            for port in ports {
                let mut servod = self.start_servod_on_port(chroot, port)?;
                let (servod_stdout, servod_stderr) = get_async_lines(&mut servod);
                let mut servod_stdout = servod_stdout.context(anyhow!("servod_stdout was None"))?;
                let mut servod_stderr = servod_stderr.context(anyhow!("servod_stdout was None"))?;
                loop {
                    let mut servod_stdout = servod_stdout.next().fuse();
                    let mut servod_stderr = servod_stderr.next().fuse();
                    select! {
                            line = servod_stderr => {
                                if let Some(line) = line {
                                    let line = line?;
                                eprintln!("{}", line);
                                    if line.contains("is busy") {
                                        break;
                                    }
                                } else {
                    return Err(anyhow!("servod failed unexpectedly"));
                                }
                            }
                            line = servod_stdout => {
                                if let Some(line) = line {
                                    let line = line?;
                                    eprintln!("{}", line);
                                    if line.contains("Listening on localhost port") {
                                        return Result::Ok(servod);
                                    }
                                } else {
                    return Err(anyhow!("servod failed unexpectedly"));
                                }
                            }
                        }
                }
            }
            return Err(anyhow!("servod failed unexpectedly"));
        })?;
        ServodConnection::from_serial(&self.serial)
    }
    pub fn is_cr50(&self) -> bool {
        self.product() == "Cr50" || self.product() == "Ti50"
    }
    pub fn is_servo(&self) -> bool {
        self.product().starts_with("Servo")
    }
    pub fn read_ec_version(&self) -> Result<String> {
        if !self.is_cr50() {
            return Err(anyhow!(
                "{} is not a Cr50, but {}",
                self.serial(),
                self.product()
            ));
        }
        retry(delay::Fixed::from_millis(500).take(2), || {
            let output = self.run_cmd("EC", "version").inspect_err(|e| {
                eprintln!("version command on EC failed: {e}");
            })?;
            RE_EC_VERSION
                .captures(&output)
                .map(|c| c["version"].trim().to_lowercase())
                .context(anyhow!("Failed to get EC version"))
                .inspect_err(|e| {
                    eprintln!("{:#?}: {output}", e);
                })
        })
        .or(Err(anyhow!("Failed to get EC version after retries")))
    }
    pub fn read_mac_addr(&self) -> Result<String> {
        if !self.is_servo() {
            return Err(anyhow!(
                "{} is not a Servo, but {}",
                self.serial(),
                self.product()
            ));
        }
        retry(delay::Fixed::from_millis(500).take(2), || {
            RE_MAC_ADDR
                .captures(&self.run_cmd("Servo EC Shell", "macaddr")?)
                .map(|c| c["addr"].to_lowercase())
                .context(anyhow!("Failed to get mac_addr of Servo"))
        })
        .or(Err(anyhow!("Failed to get mac_addr after retries")))
    }
    pub fn read_mac_addr6(&self) -> Result<MacAddr6> {
        MacAddr6::from_str(&self.read_mac_addr()?)
            .context("Failed to convert MAC address string to MacAddr6")
    }
    pub fn read_mac_addr8(&self) -> Result<MacAddr8> {
        MacAddr8::from_str(&self.read_mac_addr()?)
            .context("Failed to convert MAC address string to MacAddr8")
    }
    pub fn read_ipv6_addr(&self) -> Result<String> {
        let mac_addr = self.read_mac_addr6()?;
        let config = Config::read()?;
        let prefix = config
            .default_ipv6_prefix()
            .context("Config default_ipv6_prefix is needed")?;
        let mac_addr = mac_addr.as_bytes();
        let mut eui64_bytes = [0; 8];
        eui64_bytes.copy_from_slice(
            [&mac_addr[0..3], [0xff, 0xfe].as_slice(), &mac_addr[3..6]]
                .concat()
                .as_slice(),
        );
        eui64_bytes[0] |= 0x02; // Modified EUI-64 has universal/local bit = 1 (universal)
        Ok(format!(
            "[{}{}]",
            prefix,
            format!("{:#}", MacAddr8::from(eui64_bytes))
                .replace('.', ":")
                .to_lowercase()
        ))
    }
    pub fn read_gbb_flags(&self, repo: &str) -> Result<u64> {
        if !self.is_cr50() {
            return get_cr50_attached_to_servo(self)?.read_gbb_flags(repo);
        }
        let chroot = Chroot::new(repo)?;
        eprintln!("Reading gbb flags via Cr50...");
        chroot.exec_in_chroot(&[
            "sudo",
            "flashrom",
            "-p",
            &format!("raiden_debug_spi:target=AP,serial={}", self.serial),
            "-r",
            "-i",
            "GBB:/tmp/gbb.bin",
        ])?;
        eprintln!("Extracting gbb flags...");
        let flags =
            chroot.exec_in_chroot(&["sudo", "futility", "gbb", "-g", "--flags", "/tmp/gbb.bin"])?;
        let flags = &RE_GBB_FLAGS
            .captures(&flags)
            .context("Invalid output of futility: {flags}")?["flags"];
        u64::from_str_radix(flags, 16).context("Failed to convert value: {flags}")
    }
}
impl Display for LocalServo {
    fn fmt(&self, f: &mut Formatter) -> fmt::Result {
        write!(
            f,
            "{}",
            serde_json::to_string_pretty(&self).map_err(|_| fmt::Error)?
        )
    }
}

pub struct ServodConnection {
    serial: String,
    host: String,
    port: u16,
}
impl ServodConnection {
    pub fn from_serial(serial: &str) -> Result<Self> {
        let output = run_bash_command(&format!("ps ax | grep /servod | grep -e '-s {}' | grep -E -o -e '-p [0-9]+' | cut -d ' ' -f 2", serial), None);
        if let Ok(output) = output {
            let stdout = get_stdout(&output);
            let port = stdout.parse::<u16>()?;
            Ok(Self {
                serial: serial.to_string(),
                host: "localhost".to_string(),
                port,
            })
        } else {
            Err(anyhow!("Servod for {serial} is not running"))
        }
    }
    pub fn serial(&self) -> &str {
        &self.serial
    }
    pub fn host(&self) -> &str {
        &self.host
    }
    pub fn port(&self) -> u16 {
        self.port
    }
    pub fn run_dut_control<T: AsRef<str>>(&self, chroot: &Chroot, args: &[T]) -> Result<String> {
        eprintln!("Using servod port {:?}", self.port);
        let output = chroot.exec_in_chroot(
            &[
                ["dut-control", "-p", &self.port.to_string()].as_slice(),
                args.iter()
                    .map(AsRef::as_ref)
                    .collect::<Vec<&str>>()
                    .as_slice(),
            ]
            .concat(),
        )?;
        Ok(output)
    }
}

#[test]
fn local_servo_info_in_json() {
    let cached_info = CachedServoInfo{
        mac_addr: Some("00:00:5e:00:53:01".to_string()),
        ec_version: None
    };
    let mut tty_list = BTreeMap::new();
    tty_list.insert("Atmega UART".to_string(), "/dev/ttyUSB3".to_string());
    tty_list.insert("DUT UART".to_string(), "/dev/ttyUSB2".to_string());
    tty_list.insert("Firmware update".to_string(), "/dev/ttyUSB4".to_string());
    tty_list.insert("I2C".to_string(), "/dev/ttyUSB1".to_string());
    tty_list.insert("Servo EC Shell".to_string(), "/dev/ttyUSB0".to_string());
    let servo = LocalServo { product: "Servo V4p1".to_string(), serial: "SERVOV4P1-S-0000000000".to_string(), usb_sysfs_path: "/sys/bus/usb/devices/1-2.3".to_string(), tty_list, cached_info: Some(cached_info) };
    let serialized = format!("\n{servo}");
    assert_eq!(serialized, r#"
{
  "product": "Servo V4p1",
  "serial": "SERVOV4P1-S-0000000000",
  "usb_sysfs_path": "/sys/bus/usb/devices/1-2.3",
  "tty_list": {
    "Atmega UART": "/dev/ttyUSB3",
    "DUT UART": "/dev/ttyUSB2",
    "Firmware update": "/dev/ttyUSB4",
    "I2C": "/dev/ttyUSB1",
    "Servo EC Shell": "/dev/ttyUSB0"
  },
  "cached_info": {
    "mac_addr": "00:00:5e:00:53:01"
  }
}"#);
}
