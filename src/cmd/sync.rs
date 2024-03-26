// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

//! ## Get / update a ChromiumOS source checkout (similar to `git clone` or `git pull`)
//! ```
//! cro3 sync --cros /work/chromiumos_stable/ --version 14899.0.0
//! cro3 sync --cros /work/chromiumos_stable/ --version R110-15263.0.0
//! # following command needs a mirror repo which has cloned with --mirror option
//! cro3 sync --cros /work/chromiumos_versions/R110-15248.0.0/ --version R110-15248.0.0 --reference /work/chromiumos_mirror/
//! cro3 sync --cros /work/chromiumos_versions/R110-15248.0.0/ --version R110-15248.0.0 # you can omit --reference if the config is set
//! ```

use std::fs;
use std::path::Path;

use anyhow::bail;
use anyhow::Result;
use argh::FromArgs;
use cro3::arc::lookup_arc_version;
use cro3::arc::setup_arc_repo;
use cro3::cros::lookup_full_version;
use cro3::cros::setup_cros_repo;
use cro3::repo::get_cros_dir_unchecked;
use cro3::repo::get_current_synced_arc_version;
use cro3::repo::get_current_synced_cros_version;
use cro3::repo::get_reference_repo;
use cro3::repo::repo_sync;
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
    let is_cros = match (&args.cros, &args.arc) {
        (Some(_), None) => true,
        (None, Some(_)) => false,
        _ => bail!("Please specify either --cros or --arc."),
    };

    let version = if is_cros {
        extract_cros_version(&args.version)?
    } else {
        lookup_arc_version(&args.version)?
    };

    let repo = if is_cros {
        get_cros_dir_unchecked(&args.cros)?
    } else {
        get_cros_dir_unchecked(&args.arc)?
    };

    // Inform user of sync information.
    info!(
        "Syncing {} to {} {}",
        &repo,
        version,
        if args.force { "forcibly..." } else { "..." }
    );

    prepare_repo_paths(&repo, is_cros)?;

    // If we are using another repo as reference for rapid cloning, so make sure
    // that one is synced.
    let reference = get_reference_repo(&args.reference)?;
    if let Some(reference) = &reference {
        warn!("Updating the mirror at {reference}...");
        repo_sync(reference, args.force, args.verbose)?;
    }

    if is_cros {
        setup_cros_repo(&repo, &version, &args.reference)?;
    } else {
        setup_arc_repo(&repo, &version)?;
    }

    repo_sync(&repo, args.force, args.verbose)
}

/// Extract a appropriate version name from a argument.
fn extract_cros_version(version: &String) -> Result<String> {
    if version == "tot" {
        Ok(version.clone())
    } else {
        Ok(lookup_full_version(version, "eve")?)
    }
}

/// Prepares the repo to be synced by creating paths and reports to stderr.
fn prepare_repo_paths(repo: &str, is_cros: bool) -> Result<()> {
    if !Path::new(repo).is_dir() {
        info!("Creating {repo} ...");
        fs::create_dir_all(repo)?;
        return Ok(());
    }

    if is_cros {
        if let Ok(prev_version) = get_current_synced_cros_version(repo) {
            info!("Previous CROS version was: {}", prev_version);
            return Ok(());
        }
    } else if Path::new(&format!("{}/Android.bp", repo)).exists() {
        let prev_version = get_current_synced_arc_version(repo)?;
        info!("Previous ARC version was: {}", prev_version);
        return Ok(());
    }

    if Path::new(repo).read_dir()?.next().is_some() {
        bail!("{repo} is either not a cros, arc or is empty directory.");
    }

    Ok(())
}
