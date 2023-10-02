// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::process::Command;

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use regex_macro::regex;

use crate::util::run_bash_command;

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
        Err(anyhow!("Downloading testing_rsa failed"))
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
