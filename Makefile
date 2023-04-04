# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

RUSTFLAGS='-C target-feature=+crt-static'

build:
	@rustup -q which rustc > /dev/null || { echo "Please install rustup via https://rustup.rs/" ; exit 1 ; }
	RUSTFLAGS=$(RUSTFLAGS) cargo build --target x86_64-unknown-linux-gnu

install:
	@rustup -q which rustc > /dev/null || { echo "Please install rustup via https://rustup.rs/" ; exit 1 ; }
	RUSTFLAGS=$(RUSTFLAGS) cargo install --target x86_64-unknown-linux-gnu --path .
	file `which lium`
	ls -lah `which lium`
	echo $${SHELL} | grep bash && { lium setup bash-completion && source ~/.bash_completion ; }

check:
	cargo fmt
	cargo clippy -- -D warnings
	cargo test
	cargo check

commit:
	make check
	git add -A
	git commit

test:
	cargo test
