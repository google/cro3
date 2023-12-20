// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use anyhow::bail;
use anyhow::Result;
use argh::FromArgs;
use glob::Pattern;
use lium::cache::KvCache;
use lium::repo::get_repo_dir;
use lium::util::shell_helpers::run_bash_command;

#[derive(FromArgs, PartialEq, Debug)]
/// list supported boards
#[argh(subcommand, name = "board")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}

pub static BOARD_CACHE: KvCache<Vec<String>> = KvCache::new("board_cache");

#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    List(ArgsList),
}
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::List(args) => run_board_list(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// List up the supported boards
#[argh(subcommand, name = "list")]
pub struct ArgsList {
    /// target cros repo directory
    #[argh(option)]
    cros: Option<String>,

    /// glob pattern of the boards
    #[argh(positional)]
    filter: Option<String>,

    /// only show cached data without updating it (fast)
    #[argh(switch)]
    cached: bool,

    #[argh(option, hidden_help)]
    repo: Option<String>,
}

fn print_cached_boards(filter: &Pattern) -> Result<()> {
    let boards = BOARD_CACHE.entries()?;
    if boards.is_empty() {
        bail!("No cache found");
    }

    let mut boards: Vec<String> = boards.into_keys().collect();
    boards.sort();

    for board in boards {
        if filter.matches(&board) {
            println!("{board}");
        }
    }
    Ok(())
}

fn update_cached_boards(repodir: &str) -> Result<()> {
    let output = run_bash_command("cros query boards", Some(repodir))?;
    output.status.exit_ok()?;
    let list = String::from_utf8(output.stdout)?;
    for s in list.lines() {
        BOARD_CACHE.set(s, Vec::<String>::new())?;
    }
    Ok(())
}

fn run_board_list(args: &ArgsList) -> Result<()> {
    let filter = args
        .filter
        .as_ref()
        .map(|s| Pattern::new(s))
        .unwrap_or_else(|| Pattern::new("*"))?;

    if !args.cached {
        update_cached_boards(&get_repo_dir(&args.cros)?)?;
    }

    print_cached_boards(&filter)
}
