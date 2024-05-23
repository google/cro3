// Copyright 2024 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

//! ## Run / analyze performance experiments
//! ```
//! ```

use anyhow::Result;
use argh::FromArgs;
use cro3::chroot::Chroot;
use cro3::repo::get_cros_dir;
use tracing::warn;

use crate::cmd::tast::run_tast_test;

#[derive(FromArgs, PartialEq, Debug)]
/// Run / analyze performance experiments
#[argh(subcommand, name = "abtest")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}
impl Args {
    #[tracing::instrument(level = "trace")]
    pub fn run(&self) -> Result<()> {
        match &self.nested {
            SubCommand::Run(args) => args.run(),
        }
    }
}
#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    Run(ArgsRun),
}

#[derive(FromArgs, PartialEq, Debug)]
/// Run performance experiments
#[argh(subcommand, name = "run")]
struct ArgsRun {
    /// cros repo dir to be used
    #[argh(option)]
    cros: String,

    /// target DUT
    #[argh(option)]
    dut: String,

    /// path to a device initialization script
    #[argh(option)]
    script_init: Option<String>,

    /// path to a setup script for experiment config A
    #[argh(option)]
    script_config_a: String,

    /// path to a setup script for experiment config B
    #[argh(option)]
    script_config_b: String,

    /// tast test identifier
    #[argh(option)]
    tast_test: String,

    /// number of test runs in a row without modifying the environment
    #[argh(option)]
    run_per_cluster: Option<usize>,

    /// number of test runs in a row without modifying the environment
    #[argh(option)]
    cluster_per_group: Option<usize>,

    /// number of test runs in a row without modifying the environment
    #[argh(option)]
    group_per_iteration: Option<usize>,

    /// number of test runs in a row without modifying the environment
    #[argh(option)]
    num_of_iterations: Option<usize>,

    /// number of test runs in a row without modifying the environment
    #[argh(option)]
    experiment_name: String,

    /// number of test runs in a row without modifying the environment
    #[argh(option)]
    result_dir: Option<String>,
}
impl ArgsRun {
    fn run(&self) -> Result<()> {
        let repodir = get_cros_dir(Some(&self.cros))?;
        let chroot = Chroot::new(&repodir)?;
        run_tast_test(&chroot, &self.dut, &self.tast_test, None)?;
        Ok(())
    }
}
