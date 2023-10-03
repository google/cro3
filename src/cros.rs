// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::process::Command;

use anyhow::bail;
use anyhow::Context;
use anyhow::Result;
use regex_macro::regex;

use crate::cache::KvCache;
use crate::google_storage;
use crate::util::shell_helpers::run_bash_command;

static VERSION_TO_MILESTONE_CACHE: KvCache<String> = KvCache::new("version_cache");

// TODO #83 create an enum to represent board that can be converted to string
// (adds some type safety)
pub fn lookup_full_version(input: &str, board: &str) -> Result<String> {
    let input = input.trim();
    let re_cros_version_without_milestone = regex!(r"^\d+\.\d+\.\d+$");
    let re_cros_version = regex!(r"/(R\d+\-\d+\.\d+\.\d+)/");
    let re_full_cros_version = regex!(r"(R\d+\-\d+\.\d+\.\d+)");
    if let Some(captures) = re_full_cros_version.captures(input) {
        let captures = captures.get(1).context("No match found")?;
        Ok(captures.as_str().to_string())
    } else if re_cros_version_without_milestone.is_match(input) {
        VERSION_TO_MILESTONE_CACHE.get_or_else(input, &|key| {
            let output = google_storage::list_gs_files(&format!(
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
        bail!("Invalid version format: {}", input)
    }
}

pub fn ensure_testing_rsa_is_there() -> Result<()> {
    let cmd = "
if ! [ -f ~/.ssh/testing_rsa ]; then
    curl -s https://chromium.googlesource.com/chromiumos/chromite/+/master/ssh_keys/testing_rsa?format=TEXT | base64 --decode > ~/.ssh/testing_rsa
    chmod 600 ~/.ssh/testing_rsa
fi
";
    let output = run_bash_command(cmd, None)?;
    if output.status.success() {
        Ok(())
    } else {
        bail!("Downloading testing_rsa failed")
    }
}

pub fn setup_cros_repo(repo: &str, version: &str, reference: &Option<String>) -> Result<()> {
    let url = if version == "tot" {
        "https://chrome-internal.googlesource.com/chromeos/manifest-internal"
    } else {
        "https://chrome-internal.googlesource.com/chromeos/manifest-versions"
    };

    let mut cmd = Command::new("repo");
    cmd.current_dir(repo)
        .arg("init")
        .arg("--repo-url")
        .arg("https://chromium.googlesource.com/external/repo.git")
        .arg("-u")
        .arg(url)
        .arg("-b")
        .arg("main");

    if let Some(reference) = reference {
        eprintln!("Using {reference} as a local mirror.");
        cmd.args(["--reference", reference]);
    }

    if version != "tot" {
        let re_cros_version = regex!(r"R(\d+)\-(\d+\.\d+\.\d+)");
        let output = re_cros_version
            .captures(version.trim())
            .context("Invalid cros version")?;
        let milestone = output.get(1).context("No match found")?.as_str();
        let version = output.get(2).context("No match found")?.as_str();
        cmd.arg("-m");
        cmd.arg(format!("buildspecs/{}/{}.xml", milestone, version));
    };

    println!("Running repo init with the given version...");
    let cld = cmd.spawn().context("Failed to execute repo init")?;
    cld.wait_with_output()
        .context("Failed to wait for repo init")?;
    Ok(())
}
