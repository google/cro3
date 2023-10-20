#/bin/bash -e
# Copyright 2023 The ChromiumOS Authors
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd
TMPDIR=`mktemp -d`
if ! [ -z "$(git status --porcelain)" ]; then
	echo "Uncommited changes found. Please commit the change first."
	exit 1
fi
if ! git status | grep 'up to date' ; then
	echo "Remote branch is not up to date. Please push the commits first."
	exit 1
fi
cargo test --target-dir ${TMPDIR}
cargo build --release --target-dir ${TMPDIR}
VERSION=`${TMPDIR}/release/lium version | cut -d ' ' -f 2`

if gh release list | grep ${VERSION} ; then
	# Release with the version found. Quit.
	exit 1
fi

# Create a new release
read -r -d '' RELEASE_NOTE <<EOF
To install lium ${VERSION}, please run:
\`\`\`
curl -L -o /usr/local/bin/lium https://github.com/google/lium/releases/download/${VERSION}/lium && chmod +x /usr/local/bin/lium
\`\`\`
EOF
gh release create ${VERSION} --target `git rev-parse HEAD` --notes "${RELEASE_NOTE}" ${TMPDIR}/release/lium
