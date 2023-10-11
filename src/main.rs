// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

#![feature(exit_status_error)]
#![feature(result_option_inspect)]

use std::str::FromStr;

use anyhow::Result;
use tracing::trace;
use tracing_subscriber::{filter::LevelFilter, EnvFilter};

extern crate lazy_static;

mod cmd;

fn main() -> Result<()> {
    let args: cmd::TopLevel = argh::from_env();

    let command_line_log_level = args.verbosity.as_ref().map(|s| {
        LevelFilter::from_str(s)
            .expect("invalid log level, must be one of: trace, debug, info, warn, error")
    });

    // Set up tracing/logging.  The init call sets the global backup trace
    // logger.
    let lium_logging_env_filter = EnvFilter::builder()
        .with_env_var("LIUM_LOG")
        .with_default_directive(command_line_log_level.unwrap_or(LevelFilter::INFO).into())
        .from_env_lossy();
    tracing_subscriber::fmt()
        .with_env_filter(lium_logging_env_filter)
        .with_file(true)
        .with_line_number(true)
        .with_thread_ids(true)
        .with_level(true)
        .with_writer(std::io::stderr)
        .init();

    let args_log = &std::env::args().skip(1).collect::<Vec<_>>();
    trace!("running with args: {:?}", args_log);

    cmd::run(&args)
}
