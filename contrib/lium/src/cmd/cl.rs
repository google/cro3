// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use anyhow::Result;
use argh::FromArgs;
use lium::chroot::Chroot;
use lium::repo::get_repo_dir;

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
/// cherry-pick CLs
#[argh(subcommand, name = "pick")]
pub struct ArgsPick {
    /// target cros repo dir
    #[argh(option)]
    repo: Option<String>,

    /// dir to run git commands, relative to cros checkout (e.g. src/platform/crosvm)
    #[argh(option)]
    dir: String,

    /// CL number to checkout
    #[argh(positional)]
    cl: u64,
}
fn run_pick(args: &ArgsPick) -> Result<()> {
    let cl = args.cl;
    let dir = &args.dir;
    let chroot = Chroot::new(&get_repo_dir(&args.repo)?)?;
    chroot.run_bash_script_in_chroot(
        "checkout",
        &format!(
            r###"
gerrit --json --no-pager deps {cl} | tee tmp.txt
export REF=`cat tmp.txt | jq -r '. | map([.currentPatchSet.ref, .currentPatchSet.revision])[0][0]'`
export PROJ=`cat tmp.txt | jq -r '. | map([.currentPatchSet.ref, .currentPatchSet.revision, .project])[0][2]'`
echo ${{PROJ}} ${{REF}}
export BRANCH=`echo ${{REF}} | sed -E 's!^.*/([0-9]+)/([0-9]+)$!cl-\1_ps-\2!'`
echo ${{BRANCH}}
cd ~/chromiumos
git -C {dir} fetch https://chromium.googlesource.com/${{PROJ}} ${{REF}} &&
git -C {dir} cherry-pick FETCH_HEAD
"###,
        ),
        None,
    )?;
    Ok(())
}
