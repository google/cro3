// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

//! yet another wrapper for CrOS developers

#![feature(addr_parse_ascii)]
#![feature(exit_status_error)]
#![feature(hash_extract_if)]
#![feature(result_option_inspect)]
#![feature(assert_matches)]

pub mod abtest;
pub mod arc;
pub mod bluebench;
pub mod cache;
pub mod chroot;
pub mod config;
pub mod cros;
pub mod dut;
pub mod google_storage;
pub mod parser;
pub mod repo;
pub mod servo;
pub mod tast;
pub mod util;
