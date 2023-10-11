// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use anyhow::bail;
use anyhow::Result;
use argh::FromArgs;
use glob::Pattern;
use lium::cache::KvCache;
use lium::chroot::Chroot;
use lium::repo::get_repo_dir;

#[derive(FromArgs, PartialEq, Debug)]
/// manage modified package(s)
#[argh(subcommand, name = "packages")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}

pub static PACKAGE_CACHE: KvCache<Vec<String>> = KvCache::new("package_cache");
static DEFAULT_BOARD: &str = "host";

#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    List(ArgsList),
}
#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::List(args) => run_packages_list(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// Get package list for the target board
#[argh(subcommand, name = "list")]
pub struct ArgsList {
    /// target cros repo directory
    #[argh(option)]
    repo: Option<String>,

    /// target board (default: host)
    #[argh(option)]
    board: Option<String>,

    /// only show the cached list
    #[argh(switch)]
    cached: bool,

    /// glob pattern of the packages
    #[argh(positional)]
    packages: Option<String>,
}

fn print_cached_packages(filter: &Pattern, board: &str) -> Result<()> {
    if let Ok(Some(packages)) = PACKAGE_CACHE.get(board) {
        for t in &packages {
            if filter.matches(t) {
                println!("{t}");
            }
        }
        return Ok(());
    }
    bail!("No cache found")
}

fn update_cached_packages(repodir: &str, board: &str) -> Result<()> {
    let boardopt = if board == "host" {
        "--host".to_string()
    } else {
        format!("--build-target={}", board)
    };
    let chroot = Chroot::new(repodir)?;
    let list = chroot.exec_in_chroot(&["cros", "workon", &boardopt, "list", "--all"])?;
    let packages: Vec<String> = list.lines().map(|s| s.to_string()).collect::<Vec<_>>();
    PACKAGE_CACHE.set(board, packages)?;
    Ok(())
}

fn run_packages_list(args: &ArgsList) -> Result<()> {
    let filter = Pattern::new(args.packages.as_deref().unwrap_or("*"))?;
    let board = args.board.as_deref().unwrap_or(DEFAULT_BOARD);

    if args.cached {
        return print_cached_packages(&filter, board);
    }

    update_cached_packages(&get_repo_dir(&args.repo)?, board)?;

    print_cached_packages(&filter, board)
}
