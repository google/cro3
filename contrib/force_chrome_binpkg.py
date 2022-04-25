#!/usr/bin/env python3
#
# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Force build to use binpkgs for chromeos-chrome.

This script makes temporary local modifications to chromiumos-overlay
so that build_packages uses binpkgs for chromeos-chrome (avoiding
extremely slow source checkout and build). It also syncs the version of
chrome-icu and chromeos-lacros so that build_image doesn't fail out.

This script is totally a hack, it will not work for every use case, and
it hasn't had that much testing yet. But it might just save you an hour
or two of build time.

Prereq:

This script requires GS access. See go/chrome-linux-build#run-the-hooks
for instructions on authenticating with gsutil.

Usage:

Run this script after running `repo sync`. (And run the script again any
time you re-run `repo sync`.)

./force_chrome_binpkg.py --board <board> </path/to/chromiumos>

Running that will make local modifications to
/path/to/chromiumos/src/third_party/chromiumos-overlay.

Then run build_packages and build_image as normal in the chroot.

---

As a convenience, the script can also stash changes in
chromiumos-overlay. This can be useful to run before `repo sync`, to
clear out the script's previous changes:

./force_chrome_binpkg.py --board <board> </path/to/chromiumos> stash
"""

# pylint: disable=missing-docstring

import argparse
import os
import subprocess
from pathlib import Path


def stash_overlay_changes(src_dir):
    overlay_path = os.path.join(src_dir, 'third_party', 'chromiumos-overlay')
    cmd = ('git', 'stash')
    print(' '.join(cmd))
    subprocess.run(cmd, check=True, cwd=overlay_path)


def get_prebuilt_package_version(binhost_uri, category, package_name):
    prefix = f'{binhost_uri}/{category}/{package_name}-'
    cmd = ('gsutil.py', 'ls', f'{prefix}*')
    print(' '.join(cmd))
    output = subprocess.run(cmd, capture_output=True, check=True, text=True)
    lines = output.stdout.splitlines()
    # TODO: are there ever more than one line? This is a very minimal
    # effort sort to pick the highest number, but it's not correct
    # without parsing the version.
    line = sorted(lines)[-1]
    version = line.removeprefix(prefix).removesuffix('.tbz2')
    print(f'{package_name} version: {version}')
    return version


def get_postsubmit_binhost_uri(src_dir, board):
    # pylint: disable=line-too-long
    binhost_dir = src_dir / 'private-overlays/chromeos-partner-overlay/chromeos/binhost/target'
    board_binhost_path = binhost_dir / f'{board}-POSTSUBMIT_BINHOST.conf'
    with open(board_binhost_path) as rfile:
        board_binhost_content = rfile.read()
    board_binhost_uri = board_binhost_content.removeprefix(
        'POSTSUBMIT_BINHOST="').removesuffix('"')
    print(f'postsubmit binhost for {board}: {board_binhost_uri}')
    return board_binhost_uri


def override_package_stable_version(src_dir, category, package_name, version,
                                    board):
    # pylint: disable=line-too-long
    package_dir = src_dir / 'third_party/chromiumos-overlay' / category / package_name

    # Get the stable ebuilds.
    stable_ebuilds = [
        name for name in os.listdir(package_dir)
        if name.endswith('.ebuild') and not name.endswith('9999.ebuild')
    ]

    # Delete all stable ebuilds.
    for name in stable_ebuilds:
        path = package_dir / name
        print(f'rm {path}')
        os.remove(path)

    # Create stable ebuild contents.
    unstable_path = package_dir / f'{package_name}-9999.ebuild'
    with open(unstable_path) as rfile:
        contents = rfile.read()
    contents = contents.replace('KEYWORDS="~*"', 'KEYWORDS="*"')

    # Create new stable ebuild.
    stable_file_name = f'{package_name}-{version}.ebuild'
    stable_path = package_dir / stable_file_name
    with open(stable_path, 'w') as wfile:
        wfile.write(contents)

    # Update the manifest.
    stable_path_in_chroot = Path('../third_party/chromiumos-overlay'
                                 ) / category / package_name / stable_file_name
    cmd = ('cros_sdk', '--', 'ebuild-' + board, str(stable_path_in_chroot),
           'manifest')
    print(' '.join(cmd))
    subprocess.run(cmd, check=True, cwd=src_dir)


def main():
    action_default = 'default'
    action_stash = 'stash'

    parser = argparse.ArgumentParser()
    parser.add_argument('--board', required=True)
    parser.add_argument('chromiumos',
                        help='root of the chromiumos tree to modify')
    subparsers = parser.add_subparsers(dest='action',
                                       help='sub-command to perform')
    subparsers.add_parser(action_default, help='the default action')
    subparsers.add_parser(action_stash,
                          help='stash all changes in chromiumos-overlay')

    args = parser.parse_args()

    src_dir = Path(args.chromiumos) / 'src'

    if args.action == action_stash:
        stash_overlay_changes(src_dir)
    elif args.action is None or args.action == action_default:
        binhost_uri = get_postsubmit_binhost_uri(src_dir, args.board)

        category = 'chromeos-base'
        package_names = ('chromeos-chrome', 'chromeos-lacros', 'chrome-icu')
        for package_name in package_names:
            version = get_prebuilt_package_version(binhost_uri, category,
                                                   package_name)
            override_package_stable_version(src_dir,
                                            category,
                                            package_name,
                                            version,
                                            board=args.board)


if __name__ == '__main__':
    main()
