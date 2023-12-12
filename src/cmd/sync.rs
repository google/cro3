// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::fs;
use std::path::Path;

use anyhow::bail;
use anyhow::Result;
use argh::FromArgs;
use lium::arc::lookup_arc_version;
use lium::arc::setup_arc_repo;
use lium::cros::lookup_full_version;
use lium::cros::setup_cros_repo;
use lium::repo::get_cros_dir_unchecked;
use lium::repo::get_current_synced_arc_version;
use lium::repo::get_current_synced_version;
use lium::repo::get_reference_repo;
use lium::repo::repo_sync;
use tracing::info;
use tracing::warn;

#[derive(FromArgs, PartialEq, Debug)]
/// synchronize cros or android/arc repositories
#[argh(subcommand, name = "sync")]
pub struct Args {
    /// target cros repo dir. If omitted, current directory will be used.
    #[argh(option)]
    repo: Option<String>,

    /// path to a local reference repo to speedup syncing.
    #[argh(option)]
    reference: Option<String>,

    /// cros or android arc version to sync.
    /// e.g. for chromeOS: 14899.0.0, tot (for development)
    /// e.g. for arc: rvc, tm, master (which maps to master-arc-dev)
    #[argh(option)]
    version: String,

    /// sync arc/android instead of cros. --version will be tm or rvc
    #[argh(switch)]
    arc: bool,

    /// destructive sync
    #[argh(switch)]
    force: bool,

    /// output repo sync log as it is
    #[argh(switch)]
    verbose: bool,
}

#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    let version = extract_version(args)?;
    let repo = get_cros_dir_unchecked(&args.repo)?;

    // Inform user of sync information.
    info!(
        "Syncing {} to {} {}",
        &repo,
        version,
        if args.force { "forcibly..." } else { "..." }
    );

    // Prepare paths and determine if this is an arc or cros repo.
    let is_arc = prepare_repo_paths(&repo)?.unwrap_or(args.arc);

    // If we are using another repo as reference for rapid cloning, so make sure
    // that one is synced.
    let reference = get_reference_repo(&args.reference)?;
    if let Some(reference) = &reference {
        warn!("Updating the mirror at {reference}...");
        repo_sync(reference, args.force, args.verbose)?;
    }

    if is_arc {
        setup_arc_repo(&repo, &version)?;
    } else {
        setup_cros_repo(&repo, &version, &reference)?;
    }

    repo_sync(&repo, args.force, args.verbose)
}

/// Version string can represent either cros repo version or an arc version.
/// This function detects which and extracts its appropriately from the args.
fn extract_version(args: &Args) -> Result<String> {
    let version = if !args.arc {
        if args.version == "tot" {
            args.version.clone()
        } else {
            lookup_full_version(&args.version, "eve")?
        }
    } else {
        lookup_arc_version(&args.version)?
    };

    Ok(version)
}

/// Prepares the repo to be synced by creating paths, detecting arc or cros, and
/// reports to stderr.
///
/// returns an option of whether arc was detected.
fn prepare_repo_paths(repo: &str) -> Result<Option<bool>> {
    if !Path::new(repo).is_dir() {
        info!("Creating {repo} ...");
        fs::create_dir_all(repo)?;
        return Ok(None);
    }

    if Path::new(&format!("{}/Android.bp", repo)).exists() {
        warn!("Arc repo detected...");
        let prev_version = get_current_synced_arc_version(repo)?;
        info!("Previous ARC version was: {}", prev_version);
        return Ok(true.into());
    }

    if let Ok(prev_version) = get_current_synced_version(repo) {
        info!("Previous CROS version was: {}", prev_version);
        return Ok(false.into());
    }

    if Path::new(repo).read_dir()?.next().is_some() {
        bail!("{repo} is not a cros, arc, or empty directory.");
    }

    Ok(None)
}
