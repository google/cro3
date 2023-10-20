# Copyright 2023 The ChromiumOS Authors
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

RUSTFLAGS='-C target-feature=+crt-static'

build:
	@rustup -q which rustc > /dev/null || { echo "Please install rustup via https://rustup.rs/" ; exit 1 ; }
	RUSTFLAGS=$(RUSTFLAGS) cargo build --target x86_64-unknown-linux-gnu

release_build:
	@rustup -q which rustc > /dev/null || { echo "Please install rustup via https://rustup.rs/" ; exit 1 ; }
	RUSTFLAGS=$(RUSTFLAGS) cargo build --release --target x86_64-unknown-linux-gnu

install:
	@rustup -q which rustc > /dev/null || { echo "Please install rustup via https://rustup.rs/" ; exit 1 ; }
	RUSTFLAGS=$(RUSTFLAGS) cargo install --target x86_64-unknown-linux-gnu --path .
	@echo $$SHELL | grep bash > /dev/null && lium setup bash-completion || echo "SHELL is not Bash. Command completion will not work."
	@printf "\nlium is successfully installed at `which lium`. Try \`lium --help\` if you want!\n"

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

release:
	bash scripts/deploy_release.sh
