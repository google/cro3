// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use anyhow::Context;
use anyhow::Result;
use argh::FromArgs;
use lazy_static::lazy_static;
use lium::chroot::Chroot;
use lium::repo::get_repo_dir;
use regex::Regex;

lazy_static! {
    static ref RE_GERRIT_CL: Regex = Regex::new(r"^(?P<cl>[0-9]+)/(?P<patchset>[0-9+])$").unwrap();
}

#[derive(FromArgs, PartialEq, Debug)]
/// CL (Change List) helpers
#[argh(subcommand, name = "cl")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}
#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    Pick(ArgsPick),
}
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::Pick(args) => run_pick(args),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// cherry-pick a CL
#[argh(subcommand, name = "pick")]
pub struct ArgsPick {
    /// target cros repo dir
    #[argh(option)]
    repo: Option<String>,

    /// dir to run git commands, relative to cros checkout (e.g. src/platform/crosvm)
    #[argh(option)]
    dir: String,

    /// CLs to checkout (e.g. "4196467", "4196467/2")
    #[argh(positional)]
    cl: String,
}
fn run_pick(args: &ArgsPick) -> Result<()> {
    let capture = RE_GERRIT_CL
        .captures(&args.cl)
        .context("Invalid CL id. please specify patchset number as well (like '1234/5').")?;
    let cl = &capture["cl"];
    let cl_suffix = &cl[cl.len() - 2..];
    let patchset = &capture["patchset"];
    let dir = &args.dir;
    let chroot = Chroot::new(&get_repo_dir(&args.repo)?)?;
    chroot.run_bash_script_in_chroot(
        "checkout",
        &format!(
            r###"
cd ~/chromiumos
cd {dir}
export PROJ=`repo info . | grep -e 'Project:' | cut -d ' ' -f 2`
echo "PROJ=${{PROJ}}"
git fetch https://chromium.googlesource.com/${{PROJ}} \
  refs/changes/{cl_suffix}/{cl}/{patchset}
git cherry-pick FETCH_HEAD || git cherry-pick --abort
"###,
        ),
        None,
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn regex() {
        assert!(&RE_GERRIT_CL.captures("1234").is_none());
        assert_eq!(&RE_GERRIT_CL.captures("1234/5").unwrap()["cl"], "1234");
        assert_eq!(&RE_GERRIT_CL.captures("1234/5").unwrap()["patchset"], "5");
    }
}
