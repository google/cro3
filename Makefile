# Copyright 2023 The ChromiumOS Authors
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

RUSTFLAGS='-C target-feature=+crt-static'

.PHONY : build
build:
	@rustup -q which rustc > /dev/null || { echo "Please install rustup via https://rustup.rs/" ; exit 1 ; }
	RUSTFLAGS=$(RUSTFLAGS) cargo build --target x86_64-unknown-linux-gnu
	make doc

.PHONY : doc
doc: docs/cmdline.md

.PHONY : release_build
release_build:
	@rustup -q which rustc > /dev/null || { echo "Please install rustup via https://rustup.rs/" ; exit 1 ; }
	RUSTFLAGS=$(RUSTFLAGS) cargo build --release --target x86_64-unknown-linux-gnu

.PHONY : install
install:
	@rustup -q which rustc > /dev/null || { echo "Please install rustup via https://rustup.rs/" ; exit 1 ; }
	RUSTFLAGS=$(RUSTFLAGS) cargo install --target x86_64-unknown-linux-gnu --path .
	@echo $$SHELL | grep bash > /dev/null && cro3 setup bash-completion || echo "SHELL is not Bash. Command completion will not work."
	@printf "\ncro3 is successfully installed at `which cro3`. Try \`cro3 --help\` if you want!\n"

.PHONY : check
check:
	cargo fmt
	cargo clippy -- -D warnings
	cargo test
	cargo check

.PHONY : shellcheck
shellcheck:
	shellcheck `git ls-files *.sh *.bash`
	# - https://google.github.io/styleguide/shellguide.html#indentation
	# > Indent 2 spaces. No tabs.
	shfmt -w -i 2 .

.PHONY : commit
commit:
	make
	make check
	make shellcheck
	git add -A
	git commit

.PHONY : test
test:
	make build
	cargo test
	make cmdline_doc_check
	make bash_completion_check

.PHONY : release
release:
	bash scripts/deploy_release.sh

DOC_SRC=$(shell git ls-files src/cmd/*.rs)
docs/cmdline.md: docs/cmdline_preface.md ${DOC_SRC} Makefile
	cp docs/cmdline_preface.md $@
	@cat ${DOC_SRC} | grep '//!' | sed -E 's#^//! ?##' >> $@

.PHONY : cmdline_doc_check
cmdline_doc_check:
	./scripts/cmdline_doc_check.sh

.PHONY : bash_completion_check
bash_completion_check:
	./scripts/bash_completion_check.sh

.PHONY : preview
preview: docs/cmdline.md
	make --silent cmdline_doc_check 2>/dev/null || echo "^^^^ Warning: This warning has been ignored but please fix them before submitting!"
	gh extension exec markdown-preview docs/cmdline.md --host 0.0.0.0 || \
		echo "To install markdown-preview, run: gh extension install https://github.com/yusukebe/gh-markdown-preview | cat -"
