// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use anyhow::Result;
use argh::FromArgs;

pub mod arc;
pub mod build;
pub mod chroot;
pub mod cl;
pub mod config;
pub mod deploy;
pub mod dut;
pub mod flash;
pub mod packages;
pub mod servo;
pub mod setup;
pub mod sync;
pub mod tast;
pub mod version;
pub mod vm;

#[derive(FromArgs, PartialEq, Debug)]
/// yet another wrapper for CrOS developers.
/// For more information, see: https://github.com/google/lium
/// For Googlers, see go/lium and go/lium-bug
pub struct TopLevel {
    #[argh(option, short = 'v')]
    /// set the verbosity level for the entire program, can also be controlled
    /// with LIUM_LOG env var as described in the rust tracing crate docs
    /// https://docs.rs/tracing-subscriber/latest/tracing_subscriber/filter/struct.EnvFilter.html
    pub verbosity: Option<String>,

    #[argh(subcommand)]
    nested: Args,
}

#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
/// lium's ChromiumOS dev commands
pub enum Args {
    Arc(arc::Args),
    Build(build::Args),
    Cl(cl::Args),
    Chroot(chroot::Args),
    Config(config::Args),
    Deploy(deploy::Args),
    Dut(dut::Args),
    Flash(flash::Args),
    Packages(packages::Args),
    Servo(servo::Args),
    Setup(setup::Args),
    Sync(sync::Args),
    Tast(tast::Args),
    Version(version::Args),
    Vm(vm::Args),
}

#[tracing::instrument(level = "trace")]
pub fn run(args: &TopLevel) -> Result<()> {
    match &args.nested {
        Args::Arc(args) => arc::run(args),
        Args::Build(args) => build::run(args),
        Args::Cl(args) => cl::run(args),
        Args::Chroot(args) => chroot::run(args),
        Args::Config(args) => config::run(args),
        Args::Deploy(args) => deploy::run(args),
        Args::Dut(args) => dut::run(args),
        Args::Flash(args) => flash::run(args),
        Args::Packages(args) => packages::run(args),
        Args::Servo(args) => servo::run(args),
        Args::Setup(args) => setup::run(args),
        Args::Sync(args) => sync::run(args),
        Args::Tast(args) => tast::run(args),
        Args::Version(args) => version::run(args),
        Args::Vm(args) => vm::run(args),
    }
}
