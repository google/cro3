// Copyright 2024 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

//! ## Run / analyze performance experiments
//! ```
//! ```

use anyhow::anyhow;
use anyhow::Result;
use argh::FromArgs;
use cro3::chroot::Chroot;
use cro3::dut::SshInfo;
use cro3::repo::get_cros_dir;
use tracing::info;
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

#[derive(Debug)]
enum ExperimentConfig {
    A,
    B,
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

    /// a group contains one invocation of script_config_a (or b) and some
    /// invocation of tast_test (for run_per_cluster times)
    #[argh(option)]
    run_per_group: Option<usize>,

    /// a cluster contains some groups for config A and config B (for
    /// group_per_cluster times for each config)
    #[argh(option)]
    group_per_cluster: Option<usize>,

    /// an iteration contains one invocation of script_init and some clusters
    /// (cluster_per_iteration times)
    #[argh(option)]
    cluster_per_iteration: Option<usize>,

    /// an experiment contains some iterations (num_of_iterations times)
    #[argh(option)]
    num_of_iterations: Option<usize>,

    /// name of this experiment for identification
    #[argh(option)]
    experiment_name: String,

    /// path to a dir to store the results
    #[argh(option)]
    result_dir: Option<String>,
}
impl ArgsRun {
    fn run_group(&self, config: ExperimentConfig, dut: &SshInfo) -> Result<()> {
        let repodir = get_cros_dir(Some(&self.cros))?;
        let chroot = Chroot::new(&repodir)?;
        match config {
            ExperimentConfig::A => dut.switch_partition_set(cro3::dut::PartitionSet::Primary),
            ExperimentConfig::B => dut.switch_partition_set(cro3::dut::PartitionSet::Secondary),
        }?;
        dut.reboot()?;
        dut.wait_online()?;

        for i in 0..self.run_per_group.unwrap_or(20) {
            info!("#### run {i}");
            retry::retry(retry::delay::Fixed::from_millis(500).take(3), || {
                run_tast_test(&chroot, dut, &self.tast_test, None)
            })
            .or(Err(anyhow!("Failed to run tast test after retries")))?;
        }
        Ok(())
    }
    fn run_cluster(&self, dut: &SshInfo) -> Result<()> {
        for i in 0..self.group_per_cluster.unwrap_or(1) {
            info!("### group A-{i}");
            self.run_group(ExperimentConfig::A, dut)?;
        }
        for i in 0..self.group_per_cluster.unwrap_or(1) {
            info!("### group A-{i}");
            self.run_group(ExperimentConfig::B, dut)?;
        }
        Ok(())
    }
    fn run_iteration(&self, dut: &SshInfo) -> Result<()> {
        for i in 0..self.cluster_per_iteration.unwrap_or(1000) {
            info!("## cluster {i}");
            self.run_cluster(dut)?;
        }
        Ok(())
    }
    fn run_experiment(&self, dut: &SshInfo) -> Result<()> {
        for i in 0..self.num_of_iterations.unwrap_or(1) {
            info!("# iteration {i}");
            self.run_iteration(dut)?;
        }
        Ok(())
    }
    fn run(&self) -> Result<()> {
        let dut = SshInfo::new(&self.dut)?;
        let dut = dut.into_forwarded()?;
        self.run_experiment(dut.ssh())
    }
}
