#!/usr/bin/env bash
# Copyright 2023 The ChromiumOS Authors
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

cd "$(dirname ${BASH_SOURCE[0]})"
cd ..
echo "Project root directory is: `pwd`"

echo "Checking authentications..."
gh auth status || gh auth login
cargo owner --list || cargo login

cargo test
make release_build

VERSION=`cargo run --release -- version | cut -d ' ' -f 2 | grep -E '[0-9]+\.[0-9]+\.[0-9]'`
PROJECT_PATH=`dirname -- $(cargo locate-project --message-format plain)`
BINPATH=`readlink -f ${PROJECT_PATH}/target/x86_64-unknown-linux-gnu/release/cro3`
file ${BINPATH}
ldd ${BINPATH} | grep 'statically linked'

if gh release list | grep ${VERSION} ; then
	# Release with the version found. Quit.
	echo "release with the same version on GitHub is found. Please delete the version first by running:"
	echo "gh release delete -y ${VERSION}"
	exit 1
fi
echo "Testing and releasing ${VERSION}"

if ! [ -z "$(git status --porcelain)" ]; then
	echo "Uncommited changes found. Please commit and upload the changes first."
	exit 1
fi

if ! git status | grep 'up to date' ; then
	echo "Remote branch is not up to date. Please push the commits first."
	exit 1
fi

# Create a new release on GitHub
read -r -d '' RELEASE_NOTE <<EOF
To install cro3 ${VERSION}, please run:
\`\`\`
curl -L -o /usr/local/bin/cro3 https://github.com/google/cro3/releases/download/${VERSION}/cro3 && chmod +x /usr/local/bin/cro3
\`\`\`
EOF
echo "Creating release ${VERSION} on GitHub"
gh release create ${VERSION} --target `git rev-parse HEAD` --notes "${RELEASE_NOTE}" ./target/release/cro3

# Create a new release on crates.io
cargo publish
