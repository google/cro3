// Copyright 2025 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use anyhow::bail;
use anyhow::Result;
use argh::FromArgs;
use cro3::repo::get_cros_dir;
use cro3::util::shell_helpers::get_stdout;
use cro3::util::shell_helpers::run_bash_command;

#[derive(FromArgs, PartialEq, Debug)]
/// overlay related operations
#[argh(subcommand, name = "overlay")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}
impl Args {
    pub fn run(&self) -> Result<()> {
        match &self.nested {
            SubCommand::Show(args) => args.run(),
        }
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// show overlay information
#[argh(subcommand, name = "show")]
pub struct ShowCmd {
    /// target cros repo directory
    #[argh(option)]
    cros: Option<String>,

    /// a BOARD name to be displayed
    #[argh(option)]
    board: String,
}
impl ShowCmd {
    pub fn run(&self) -> Result<()> {
        let out = run_bash_command(
            "cros query boards -o '{name} {top_level_overlay}'",
            Some(get_cros_dir(&self.cros)?.as_str()),
        )?;
        let list = get_stdout(&out);
        let list: Vec<(String, String)> = list
            .trim()
            .split("\n")
            .map(|s| {
                let (board, overlay_path) = s.split_once(' ').unwrap_or(("", ""));
                (board.to_string(), overlay_path.to_string())
            })
            .collect();
        if let Some((board, overlay_path)) = list.iter().find(|s| s.0 == self.board) {
            println!("BOARD={board} is defined by {overlay_path}");
        } else {
            bail!("board {} not found", self.board);
        }
        Ok(())
    }
}

#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    Show(ShowCmd),
}
