// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

#![feature(exit_status_error)]
#![feature(result_option_inspect)]

use std::process::Command;

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use lium::cache::KvCache;
use regex_macro::regex;

extern crate lazy_static;

mod cmd;

static VERSION_TO_MILESTONE_CACHE: KvCache<String> = KvCache::new("version_cache");

fn list_gs_files(pattern: &str) -> Result<String> {
    let cmd = format!("gsutil.py ls {}", pattern.trim());
    println!("{:?}", cmd);
    let output = Command::new("bash").arg("-c").arg(cmd).output().context(
        "Failed to execute gsutil ls (maybe you need depot_tools and/or `gsutil.py config` with \
         'chromeos-swarming' project)",
    )?;
    Ok(String::from_utf8_lossy(&output.stdout)
        .to_string()
        .trim()
        .to_string())
}

fn lookup_full_version(input: &str, board: &str) -> Result<String> {
    let input = input.trim();
    let re_cros_version_without_milestone = regex!(r"^\d+\.\d+\.\d+$");
    let re_cros_version = regex!(r"/(R\d+\-\d+\.\d+\.\d+)/");
    let re_full_cros_version = regex!(r"(R\d+\-\d+\.\d+\.\d+)");
    if let Some(captures) = re_full_cros_version.captures(input) {
        let captures = captures.get(1).context("No match found")?;
        Ok(captures.as_str().to_string())
    } else if re_cros_version_without_milestone.is_match(input) {
        VERSION_TO_MILESTONE_CACHE.get_or_else(input, &|key| {
            let output = list_gs_files(&format!(
                "gs://chromeos-image-archive/{}-release/R*-{}/chromiumos_test_image.tar.xz",
                board, key
            ))
            .context(
                "gsutil command failed (maybe you need depot_tools and/or `gsutil.py config` with \
                 'chromeos-swarming' project)",
            )?;
            let output = re_cros_version
                .captures(output.trim())
                .context("Invalid gsutil output")?;
            let output = output.get(1).context("No match found")?;
            Ok(output.as_str().to_string())
        })
    } else {
        Err(anyhow!("Invalid version format: {}", input))
    }
}

fn main() -> Result<()> {
    let args: cmd::TopLevel = argh::from_env();
    cmd::run(&args)
}
