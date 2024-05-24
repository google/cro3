// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

#![feature(exit_status_error)]
#![feature(result_option_inspect)]

use std::process::ExitCode;
use std::str::FromStr;

use tracing::error;
use tracing::trace;
use tracing_subscriber::filter::LevelFilter;
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;
use tracing_subscriber::EnvFilter;

extern crate lazy_static;

mod cmd;

fn main() -> ExitCode {
    let args: cmd::TopLevel = argh::from_env();

    let command_line_log_level = args.verbosity.as_ref().map(|s| {
        LevelFilter::from_str(s)
            .expect("invalid log level, must be one of: trace, debug, info, warn, error")
    });

    // Set up tracing/logging.  The init call sets the global backup trace
    // logger.
    let cro3_logging_env_filter = EnvFilter::builder()
        .with_env_var("CRO3_LOG")
        .with_default_directive(command_line_log_level.unwrap_or(LevelFilter::INFO).into())
        .from_env_lossy();
    let tracing_subscriber = tracing_subscriber::fmt::layer()
        .with_file(true)
        .with_line_number(true)
        .with_thread_ids(true)
        .with_level(true)
        .with_writer(std::io::stderr);
    tracing_subscriber::registry()
        .with(tracing_subscriber)
        .with(cro3_logging_env_filter)
        .init();

    let args_log = &std::env::args().skip(1).collect::<Vec<_>>();
    trace!("running with args: {:?}", args_log);

    if args_log.contains(&"--repo".to_string()) {
        panic!(
            "--repo option was renamed to --cros/--arc option. `cro3 {} --help` has more details.",
            args_log[0]
        );
    }

    if let Err(e) = cmd::run(&args) {
        error!("{e:#}");
        ExitCode::FAILURE
    } else {
        ExitCode::SUCCESS
    }
}
