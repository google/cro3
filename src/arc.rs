// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::process::Command;

use anyhow::bail;
use anyhow::Context;
use anyhow::Result;

use crate::config::Config;
use crate::util::shell_helpers::launch_command_with_stdout_label;

const MASTER_ARC_DEV: &str = "master";
const RVC: &str = "rvc";
const TM: &str = "tm";

pub fn lookup_arc_version(input: &str) -> Result<String> {
    // TODO: find a way to get available version name
    match input {
        MASTER_ARC_DEV | RVC | TM => Ok(input.to_string()),
        _ => bail!("Invalid ARC version : {}", input),
    }
}

fn arc_version_to_branch_name(version: &str) -> Result<String> {
    match version {
        RVC | TM => Ok(format!("{}-arc", version).to_owned()),
        MASTER_ARC_DEV => Ok("master-arc-dev".to_owned()),
        _ => bail!("Invalid ARC version: {}", version),
    }
}

pub fn setup_arc_repo(repo: &str, version: &str) -> Result<()> {
    println!("Running repo init with the given version...");
    let config = Config::read()?;
    let manifest_url = config
        .android_manifest_url()
        .context("Please configure android_manifest_url")?;
    let branch = arc_version_to_branch_name(version)?;

    launch_command_with_stdout_label(
        Command::new("repo").current_dir(repo).args([
            "init",
            "-c",
            "-u",
            &manifest_url,
            "-b",
            &branch,
            "--use-superproject",
            "--partial-clone",
            "--partial-clone-exclude=platform/frameworks/base",
            "--clone-filter=blob:limit=10M",
        ]),
        "repo init".to_string().into(),
    )?;

    Ok(())
}
