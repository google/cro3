# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

RUSTFLAGS='-C target-feature=+crt-static'

install:
	@rustup -q which rustc > /dev/null || { echo "Please install rustup via https://rustup.rs/" ; exit 1 ; }
	RUSTFLAGS=$(RUSTFLAGS) cargo install --path . --target x86_64-unknown-linux-gnu
	file `which lium`
	ls -lah `which lium`

run:
	make build_static
	scp target/x86_64-unknown-linux-gnu/release/lium tok-satlab1:~/
	ssh tok-satlab1 -- /usr/local/bin/docker run --rm -it -d --name lium --privileged ubuntu:latest || echo "skipping docker run"
	# `docker exec -ti lium /bin/bash` on satlab to get into lium container
	ssh tok-satlab1 -- /usr/local/bin/docker exec lium apt update
	ssh tok-satlab1 -- /usr/local/bin/docker exec lium apt install -y socat iproute2 minicom usbutils
	ssh tok-satlab1 -- /usr/local/bin/docker cp ./lium lium:/bin/
	ssh tok-satlab1 -- /usr/local/bin/docker exec lium lium servo list --json > servo_list_tok-satlab1.json

deploy: build_static
ifndef DUT
	$(error Please set DUT to deploy)
endif
	lium dut push $(DUT) --dest '~' target/x86_64-unknown-linux-gnu/release/lium

setup:
	rustup update

commit:
	cargo clippy -- -D warnings
	cargo test
	cargo build
	git add -A
	git commit

test:
	cargo test

integration_test:
	make install
	lium build_packages --repo /work/chromiumos_stable --board octopus --workon 'third-party-crates-src crosvm vm_host_tools chromeos-kernel-4_14'
