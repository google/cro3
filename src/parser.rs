// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

//! This module is used to get Linux System Base (LSB) release information on
//! Chrome OS systems, as usually located in `/etc/lsb-release`.

//! This file is a fork of:
//! https://source.chromium.org/chromium/chromiumos/platform2/+/main:vm_tools/crostini_client/lsb_release.rs;drc=41a92137d3e795ad6a51c5dec90dfa142af8c7c3

use std::collections::BTreeMap;
use std::error::Error;
use std::fmt::{self, Display, Formatter};
use std::result::Result;
use std::str::FromStr;

const CHROMEOS_RELEASE_TRACK_KEY: &str = "CHROMEOS_RELEASE_TRACK";

/// An error generated while gathering release information.
#[derive(Debug)]
pub enum LsbReleaseError {
    ParseError { row: usize, message: &'static str },
}

impl Display for LsbReleaseError {
    fn fmt(&self, f: &mut Formatter) -> fmt::Result {
        use self::LsbReleaseError::*;

        match self {
            ParseError { row, message } => write!(f, "parse error at row {}: {}", row, message),
        }
    }
}

impl Error for LsbReleaseError {}

/// A result from gathering resource information.
pub type LsbReleaseResult<T> = Result<T, LsbReleaseError>;

/// Release information typically gathered from the environment or from
/// `/etc/lsb-release`.
#[derive(Debug)]
pub struct LsbRelease {
    info: BTreeMap<String, String>,
}

impl LsbRelease {
    /// Gets arbitrary release information, or none if unavailable.
    pub fn get<K: AsRef<str>>(&self, k: K) -> Option<&str> {
        self.info.get(k.as_ref()).map(|s| s.as_str())
    }

    /// Gets the type of release channel this release information corresponds
    /// to, or none if this
    /// information was not indicated.
    pub fn release_channel(&self) -> Option<ReleaseChannel> {
        self.get(CHROMEOS_RELEASE_TRACK_KEY).map(|c| c.into())
    }
}

impl FromStr for LsbRelease {
    type Err = LsbReleaseError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        let mut info = BTreeMap::new();
        for (row, line) in s.lines().enumerate() {
            let line_trimmed = line.trim();
            if line_trimmed.is_empty() {
                continue;
            }
            // Attempt to match exactly two parts of the line,
            // before and after the equals sign.
            let mut line_parts = line_trimmed.splitn(2, '=');
            match (line_parts.next(), line_parts.next()) {
                (Some(key), Some(value)) => {
                    if info.insert(key.to_owned(), value.to_owned()).is_some() {
                        return Err(LsbReleaseError::ParseError {
                            row,
                            message: "duplicate key in row",
                        });
                    }
                }
                _ => {
                    return Err(LsbReleaseError::ParseError {
                        row,
                        message: "missing '=' in row",
                    });
                }
            }
        }
        Ok(LsbRelease { info })
    }
}

/// A channel of OS releases. Channels are distinguished by their relative
/// stability and frequency of release.
#[derive(PartialEq, Eq, Debug)]
pub enum ReleaseChannel<'a> {
    Lts,
    Ltc,
    Stable,
    Beta,
    Dev,
    Canary,
    /// Typically indicates that this release does not correspond to an
    /// official release channel. An
    /// example of this would be `testimage-channel`.
    Other(&'a str),
}

impl<'a> From<&'a str> for ReleaseChannel<'a> {
    fn from(s: &str) -> ReleaseChannel {
        use self::ReleaseChannel::*;
        match s {
            "lts-channel" => Lts,
            "ltc-channel" => Ltc,
            "stable-channel" => Stable,
            "beta-channel" => Beta,
            "dev-channel" => Dev,
            "canary-channel" => Canary,
            _ => Other(s),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const LSB_RELEASE: &str = r#"
            CHROMEOS_RELEASE_APPID={495DCB07-E19A-4D7D-99B9-4710011A65B1}
            CHROMEOS_BOARD_APPID={495DCB07-E19A-4D7D-99B9-4710011A65B1}
            CHROMEOS_CANARY_APPID={90F229CE-83E2-4FAF-8479-E368A34938B1}
            DEVICETYPE=CHROMEBOOK
            CHROMEOS_RELEASE_BUILDER_PATH=nami-paladin/R73-11438.0.0-rc1
            CHROMEOS_RELEASE_BOARD=nami
            CHROMEOS_RELEASE_BRANCH_NUMBER=0
            CHROMEOS_RELEASE_TRACK=testimage-channel
            CHROMEOS_RELEASE_DESCRIPTION=11438.0.0-rc1 (Continuous Builder - Builder: N/A) nami
            CHROMEOS_RELEASE_NAME=Chromium OS
            CHROMEOS_AUSERVER=http://swarm-cros-457.c.chromeos-bot.internal:8080/update
            CHROMEOS_ARC_VERSION=5193302
            CHROMEOS_ARC_ANDROID_SDK_VERSION=25
            GOOGLE_RELEASE=11438.0.0-rc1
            CHROMEOS_DEVSERVER=http://swarm-cros-457.c.chromeos-bot.internal:8080
            CHROMEOS_RELEASE_BUILD_NUMBER=11438
            CHROMEOS_RELEASE_CHROME_MILESTONE=73
            CHROMEOS_RELEASE_PATCH_NUMBER=0-rc1
            CHROMEOS_RELEASE_BUILD_TYPE=Continuous Builder - Builder: N/A
            CHROMEOS_RELEASE_UNIBUILD=1
            CHROMEOS_RELEASE_VERSION=11438.0.0-rc1"#;

    #[test]
    fn parse() {
        let lsb_release = LSB_RELEASE.parse::<LsbRelease>().unwrap();
        assert_eq!(
            lsb_release.get("CHROMEOS_RELEASE_APPID"),
            Some("{495DCB07-E19A-4D7D-99B9-4710011A65B1}")
        );
        assert_eq!(lsb_release.get("DEVICETYPE"), Some("CHROMEBOOK"));
        assert_eq!(
            lsb_release.get("CHROMEOS_RELEASE_VERSION"),
            Some("11438.0.0-rc1")
        );
        assert_eq!(lsb_release.info.len(), LSB_RELEASE.lines().count() - 1);
    }

    #[test]
    fn invalid_parse() {
        assert!("SOMETHING_SOMETHING".parse::<LsbRelease>().is_err());
        assert!("A=1\nA=2".parse::<LsbRelease>().is_err());
    }

    #[test]
    fn release_channel() {
        let lsb_release = "CHROMEOS_RELEASE_TRACK=testimage-channel"
            .parse::<LsbRelease>()
            .unwrap();
        assert_eq!(
            lsb_release.release_channel(),
            Some(ReleaseChannel::Other("testimage-channel"))
        );
        let lsb_release = "CHROMEOS_RELEASE_TRACK=canary-channel"
            .parse::<LsbRelease>()
            .unwrap();
        assert_eq!(lsb_release.release_channel(), Some(ReleaseChannel::Canary));
        let lsb_release = "CHROMEOS_RELEASE_TRACK=dev-channel"
            .parse::<LsbRelease>()
            .unwrap();
        assert_eq!(lsb_release.release_channel(), Some(ReleaseChannel::Dev));
        let lsb_release = "CHROMEOS_RELEASE_TRACK=beta-channel"
            .parse::<LsbRelease>()
            .unwrap();
        assert_eq!(lsb_release.release_channel(), Some(ReleaseChannel::Beta));
        let lsb_release = "CHROMEOS_RELEASE_TRACK=stable-channel"
            .parse::<LsbRelease>()
            .unwrap();
        assert_eq!(lsb_release.release_channel(), Some(ReleaseChannel::Stable));
        let lsb_release = "CHROMEOS_RELEASE_TRACK=ltc-channel"
            .parse::<LsbRelease>()
            .unwrap();
        assert_eq!(lsb_release.release_channel(), Some(ReleaseChannel::Ltc));
        let lsb_release = "CHROMEOS_RELEASE_TRACK=lts-channel"
            .parse::<LsbRelease>()
            .unwrap();
        assert_eq!(lsb_release.release_channel(), Some(ReleaseChannel::Lts));
    }
}
