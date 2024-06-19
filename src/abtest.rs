use std::fmt::Display;
use std::fs;
use std::io::Write;
use std::path::PathBuf;

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;
use serde::Deserialize;
use serde::Serialize;
use tracing::info;
use tracing::warn;

use crate::dut::PartitionSet;
use crate::dut::SshInfo;
use crate::tast::run_tast_test;
use crate::tast::TastTestExecutionType;

#[derive(Debug, Serialize, Deserialize, Clone, Eq, PartialEq, Ord, PartialOrd, Hash, Copy)]
pub enum ExperimentConfig {
    A,
    B,
}
impl Display for ExperimentConfig {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            match self {
                ExperimentConfig::A => 'A',
                ExperimentConfig::B => 'B',
            }
        )
    }
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ExperimentRunMetadata {
    pub runner: ExperimentRunner,
    iteration: usize,
    cluster: usize,
    pub config: ExperimentConfig,
    group: usize,
    run: usize,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ExperimentRunParameter {
    pub run_per_group: usize,
    pub group_per_cluster: usize,
    pub cluster_per_iteration: usize,
    pub num_of_iterations: usize,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ExperimentRunner {
    tast: TastTestExecutionType,
    pub experiment_name: String,
    ssh: SshInfo,
    dut_id: String,
    #[serde(flatten)]
    pub params: ExperimentRunParameter,
    pub tast_test: String,
    results_dir: PathBuf,
}
impl ExperimentRunner {
    pub fn new(
        tast: TastTestExecutionType,
        experiment_name: String,
        ssh: SshInfo,
        dut_id: String,
        params: ExperimentRunParameter,
        tast_test: String,
        results_dir: PathBuf,
    ) -> Self {
        Self {
            tast,
            experiment_name,
            ssh,
            dut_id,
            params,
            tast_test,
            results_dir,
        }
    }
    fn run_group(
        &self,
        iteration: usize,
        cluster: usize,
        config: ExperimentConfig,
        group: usize,
    ) -> Result<()> {
        match config {
            ExperimentConfig::A => self.ssh.switch_partition_set(PartitionSet::A),
            ExperimentConfig::B => self.ssh.switch_partition_set(PartitionSet::B),
        }?;
        if let Err(e) = self.ssh.reboot() {
            warn!("reboot failed (ignored): {e:?}");
        }
        self.ssh.wait_online()?;

        for i in 0..self.params.run_per_group {
            info!("#### run {i} with {}", self.dut_id);
            let mut result_dir = self.results_dir.clone();
            result_dir.push(format!(
                "{}_{}_i{iteration}_c{cluster}_g{config}{group}_{}",
                self.experiment_name,
                self.dut_id,
                chrono::Local::now().format("%Y%m%d_%H%M%S_%f"),
            ));
            let run_metadata = ExperimentRunMetadata {
                runner: (*self).clone(),
                iteration,
                cluster,
                config: config.clone(),
                group,
                run: i,
            };
            fs::create_dir_all(&result_dir).context("Failed to create the result dir")?;
            let mut file = fs::File::create(&result_dir.join("cro3_abtest_run_metadata.json"))?;
            write!(file, "{}", serde_json::to_string(&run_metadata)?)?;
            let mut retry_count = 0;
            retry::retry(retry::delay::Fixed::from_millis(500).take(3), || {
                info!("retry_count: {retry_count}");
                retry_count += 1;
                run_tast_test(
                    &self.ssh,
                    &self.tast,
                    &self.tast_test,
                    Some(format!("-resultsdir {}", result_dir.to_string_lossy()).as_str()),
                )
            })
            .or(Err(anyhow!("Failed to run tast test after retries")))?;
        }
        Ok(())
    }
    fn run_cluster(&self, iteration: usize, cluster: usize) -> Result<()> {
        for i in 0..self.params.group_per_cluster {
            info!("### group A-{i}");
            self.run_group(iteration, cluster, ExperimentConfig::A, i)?;
        }
        for i in 0..self.params.group_per_cluster {
            info!("### group B-{i}");
            self.run_group(iteration, cluster, ExperimentConfig::B, i)?;
        }
        Ok(())
    }
    fn run_iteration(&self, iteration: usize) -> Result<()> {
        for i in 0..self.params.cluster_per_iteration {
            info!("## cluster {i}");
            self.run_cluster(iteration, i)?;
        }
        Ok(())
    }
    pub fn run_experiment(&self) -> Result<()> {
        for i in 0..self.params.num_of_iterations {
            info!("# iteration {i}");
            self.run_iteration(i)?;
        }
        Ok(())
    }
}
