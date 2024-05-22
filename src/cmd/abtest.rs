// Copyright 2024 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

//! ## Run / analyze performance experiments
//! ```
//! ```

use std::collections::HashMap;
use std::env::current_exe;
use std::fs::read_to_string;
use std::io::stdout;
use std::io::Read;
use std::io::Write;
use std::thread;
use std::time;

use anyhow::anyhow;
use anyhow::bail;
use anyhow::Context;
use anyhow::Result;
use argh::FromArgs;
use cro3::chroot::Chroot;
use cro3::cros;
use cro3::dut::discover_local_nodes;
use cro3::dut::fetch_dut_info_in_parallel;
use cro3::dut::register_dut;
use cro3::dut::DutInfo;
use cro3::dut::MonitoredDut;
use cro3::dut::SshInfo;
use cro3::dut::SSH_CACHE;
use cro3::repo::get_cros_dir;
use cro3::servo::get_cr50_attached_to_servo;
use cro3::servo::LocalServo;
use cro3::servo::ServoList;
use lazy_static::lazy_static;
use rayon::prelude::*;
use termion::screen::IntoAlternateScreen;
use tracing::error;
use tracing::info;
use tracing::warn;

#[derive(FromArgs, PartialEq, Debug)]
/// Run / analyze performance experiments
#[argh(subcommand, name = "abtest")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}
#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    Run(ArgsRun),
}
#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::Run(args) => args.run(),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// Run performance experiments
#[argh(subcommand, name = "run")]
struct ArgsRun {
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

    /// path to a test script
    #[argh(option)]
    script_test: String,

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
    result_dir: String,
}
impl ArgsRun {
    fn run(&self) -> Result<()> {
        cros::ensure_testing_rsa_is_there()?;
        let target = &SshInfo::new(&self.dut)?;
        Ok(())
    }
}
