// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use crate::util::get_stdout;
use crate::util::run_bash_command;
use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use regex_macro::regex;
use std::env;
use std::path::PathBuf;
use std::process::exit;
use std::process::Command;
use std::process::Stdio;

fn is_cros_dir(dir: &str) -> bool {
    let path = PathBuf::from(dir);
    path.is_dir() && path.join(".repo").is_dir() && path.join("chromite").join("bin").is_dir()
}

pub fn get_cros_dir_unchecked(dir: &Option<String>) -> Result<String> {
    let crosdir = if let Some(cros) = dir {
        cros.to_string()
    } else {
        env::current_dir()?.to_string_lossy().to_string()
    };
    Ok(crosdir)
}

pub fn get_repo_dir(dir: &Option<String>) -> Result<String> {
    let repo = get_cros_dir_unchecked(dir)?;
    if is_cros_dir(&repo) {
        Ok(repo)
    } else {
        Err(anyhow!("{repo} is not a ChromeOS direcotry!"))
    }
}

pub fn get_current_synced_version(repo: &str) -> Result<String> {
    let cmd = "./src/third_party/chromiumos-overlay/chromeos/config/chromeos_version.sh | grep -e VERSION_STRING -e CHROME_BRANCH | cut -d '=' -f 2 | cut -d '-' -f 1";
    let output = run_bash_command(cmd, Some(repo))?;
    let binding = get_stdout(&output);
    let output: Vec<&str> = binding.split('\n').collect();
    let version = format!("R{}-{}", output[0], output[1]);
    let re_cros_version = regex!(r"R\d+\-\d+\.\d+\.\d+");
    if re_cros_version.is_match(&version) {
        Ok(version)
    } else {
        Err(anyhow!("Invalid version format: {}", version))
    }
}

pub fn get_current_synced_arc_version(repo: &str) -> Result<String> {
    // TODO: Are there any better way to do?
    let cmd = "cd .repo/manifests && git branch -r --contains HEAD | xargs -n 1 | grep m/ | sed -E 's@m/(.*)-arc@\\1@g'";
    let output = run_bash_command(cmd, Some(repo))?;
    Ok(get_stdout(&output))
}

pub fn repo_sync(repo: &str, force: bool) -> Result<()> {
    let mut last_failed_repos = None;

    loop {
        println!("Running repo sync...");
        let cmd = Command::new("repo")
            .current_dir(repo)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .args(["sync", "-j", "16"])
            .spawn()
            .context("Failed to execute repo sync")?;
        let result = cmd
            .wait_with_output()
            .context("Failed to wait for repo sync")?;
        if !result.status.success() {
            println!("repo sync failed.");
            let stderr = String::from_utf8_lossy(&result.stderr)
                .to_string()
                .trim()
                .to_string();
            let it = stderr
                .split('\n')
                .skip_while(|e| !e.contains("Failing repos:"));
            let repos: Vec<String> = it.map(|e| e.to_string()).collect();
            let repos = repos[1..=repos.len() - 2].to_owned();
            println!("Failed repos: {:?}", &repos);
            if !force {
                break;
            }
            if Some(&repos) == last_failed_repos.as_ref() {
                println!("Repo is failing with the same set of the repos, aborting...");
                exit(1);
            }
            for dir in &repos {
                let cmd = Command::new("rm")
                    .current_dir(repo)
                    .args(["-rf", dir])
                    .spawn()
                    .context("Failed to execute rm")?;
                let result = cmd.wait_with_output().context("Failed to wait for rm")?;
                if result.status.success() {
                    println!("repo {} was deleted", dir);
                } else {
                    return Err(anyhow!("rm exited with {:?}", result.status));
                }
            }
            last_failed_repos = Some(repos.to_owned());
            continue;
        }
        break;
    }
    println!("repo sync done!");
    Ok(())
}
