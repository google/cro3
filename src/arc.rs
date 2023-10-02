// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::process::Command;

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;

use crate::config::Config;

pub fn lookup_arc_version(input: &str) -> Result<String> {
    // TODO: find a way to get available version name
    if input == "tm" || input == "rvc" {
        Ok(input.to_string())
    } else {
        Err(anyhow!("Invalid ARC version : {}", input))
    }
}

pub fn setup_arc_repo(repo: &str, version: &str) -> Result<()> {
    println!("Running repo init with the given version...");
    let config = Config::read()?;
    let manifest_url = config
        .android_manifest_url()
        .context("Please configure android_manifest_url")?;
    let cmd = Command::new("repo")
        .current_dir(repo)
        .args([
            "init",
            "-c",
            "-u",
            &manifest_url,
            "-b",
            format!("{}-arc", version).as_str(),
            "--use-superproject",
            "--partial-clone",
            "--partial-clone-exclude=platform/frameworks/base",
            "--clone-filter=blob:limit=10M",
        ])
        .spawn()
        .context("Failed to execute repo init")?;
    cmd.wait_with_output()
        .context("Failed to wait for repo init")?;
    Ok(())
}
