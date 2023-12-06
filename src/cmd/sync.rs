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
    cros: Option<String>,

    /// target android repo dir. If omitted, current directory will be used.
    /// When this flag is specified, --version option can be the branch name to
    /// sync to.
    #[argh(option)]
    arc: Option<String>,

    /// path to a local reference repo to speedup syncing.
    #[argh(option)]
    reference: Option<String>,

    /// cros or android arc version to sync.
    /// e.g. for chromeOS: 14899.0.0, tot (for development)
    /// e.g. for arc: rvc, tm, master (which maps to master-arc-dev)
    #[argh(option)]
    version: String,

    /// destructive sync
    #[argh(switch)]
    force: bool,

    /// output repo sync log as it is
    #[argh(switch)]
    verbose: bool,

    #[argh(option, hidden_help)]
    repo: Option<String>,
}

#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    let is_arc = match (&args.cros, &args.arc) {
        (Some(_), None) => false,
        (None, Some(_)) => true,
        _ => bail!("Please specify either --cros or --arc."),
    };

    let version = if is_arc {
        lookup_arc_version(&args.version)?
    } else {
        extract_cros_version(&args.version)?
    };

    let repo = if is_arc {
        get_cros_dir_unchecked(&args.arc)?
    } else {
        get_cros_dir_unchecked(&args.cros)?
    };

    // Inform user of sync information.
    info!(
        "Syncing {} to {} {}",
        &repo,
        version,
        if args.force { "forcibly..." } else { "..." }
    );

    if is_arc {
        prepare_arc_repo_paths(&repo)?;
    } else {
        prepare_cros_repo_paths(&repo)?;
    }

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
fn extract_cros_version(version: &String) -> Result<String> {
    if version == "tot" {
        Ok(version.clone())
    } else {
        Ok(lookup_full_version(version, "eve")?)
    }
}

/// Prepares the repo to be synced by creating paths, detecting arc or cros, and
/// reports to stderr.
///
/// returns an option of whether arc was detected.
fn prepare_cros_repo_paths(repo: &str) -> Result<()> {
    if !Path::new(repo).is_dir() {
        info!("Creating {repo} ...");
        fs::create_dir_all(repo)?;
        return Ok(());
    }

    if let Ok(prev_version) = get_current_synced_version(repo) {
        info!("Previous CROS version was: {}", prev_version);
        return Ok(());
    }

    if Path::new(repo).read_dir()?.next().is_some() {
        bail!("{repo} is either not a cros or is empty directory.");
    }

    Ok(())
}

fn prepare_arc_repo_paths(repo: &str) -> Result<()> {
    if !Path::new(repo).is_dir() {
        info!("Creating {repo} ...");
        fs::create_dir_all(repo)?;
        return Ok(());
    }

    if Path::new(&format!("{}/Android.bp", repo)).exists() {
        let prev_version = get_current_synced_arc_version(repo)?;
        info!("Previous ARC version was: {}", prev_version);
        return Ok(());
    }

    if Path::new(repo).read_dir()?.next().is_some() {
        bail!("{repo} is either not a arc or empty directory.");
    }

    Ok(())
}
