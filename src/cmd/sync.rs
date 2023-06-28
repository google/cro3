// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use crate::lookup_full_version;
use anyhow::anyhow;
use anyhow::Result;
use argh::FromArgs;
use lium::arc::lookup_arc_version;
use lium::arc::setup_arc_repo;
use lium::cros::setup_cros_repo;
use lium::repo::get_cros_dir_unchecked;
use lium::repo::get_current_synced_arc_version;
use lium::repo::get_current_synced_version;
use lium::repo::repo_sync;
use std::fs;
use std::path::Path;

#[derive(FromArgs, PartialEq, Debug)]
/// smart repo sync wrapper
#[argh(subcommand, name = "sync")]
pub struct Args {
    /// target cros repo dir. If omitted, current directory will be used.
    #[argh(option)]
    repo: Option<String>,

    /// path to a local reference repo to speedup syncing.
    #[argh(option)]
    reference: Option<String>,

    /// cros version to sync. e.g. 14899.0.0, tot (for development)
    #[argh(option)]
    version: String,

    /// sync to arc instead of cros. --version will be tm or rvc
    #[argh(switch)]
    arc: bool,

    /// destructive sync
    #[argh(switch)]
    force: bool,
}

pub fn run(args: &Args) -> Result<()> {
    let mut is_arc = args.arc;
    let version = if !is_arc {
        if args.version == "tot" {
            args.version.clone()
        } else {
            lookup_full_version(&args.version, "eve")?
        }
    } else {
        lookup_arc_version(&args.version)?
    };
    let repo = get_cros_dir_unchecked(&args.repo)?;

    eprint!("Syncing {} to {} ", &repo, version);
    if args.force {
        eprintln!("forcibly ...");
    } else {
        eprintln!("...");
    }

    if !Path::new(&repo).is_dir() {
        eprintln!("Creating {repo} ...");
        fs::create_dir_all(&repo)?;
    } else if Path::new(&format!("{}/Android.bp", &repo)).exists() {
        let prev_version = get_current_synced_arc_version(&repo)?;
        eprintln!("Previous ARC version was: {}", prev_version);
        is_arc = true;
    } else if let Ok(prev_version) = get_current_synced_version(&repo) {
        eprintln!("Previous CROS version was: {}", prev_version);
        is_arc = false;
    } else if Path::new(&repo).read_dir()?.next().is_some() {
        return Err(anyhow!(
            "{repo} is not a cros directory nor an empty directory."
        ));
    }
    if let Some(reference) = &args.reference {
        eprintln!("Updating the mirror at {reference}...");
        repo_sync(reference, args.force)?;
    }
    if is_arc {
        setup_arc_repo(&repo, &version)?;
    } else {
        setup_cros_repo(&repo, &version, &args.reference)?;
    }

    repo_sync(&repo, args.force)
}
