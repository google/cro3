#!/usr/bin/env python3
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
from collections import defaultdict
import json
import os
import subprocess
import sys
import tempfile

from pathlib import Path
from chromite.lib.cros_build_lib import IsInsideChroot

user_conf = '/etc/make.conf.user'
old_conf_line = 'source ${ROOT}/etc/make.conf.binhost'
conf_line = 'source /etc/binhost/${BOARD_USE}'

def run_prechecks():
    if not IsInsideChroot():
        print('This script must be run inside the CrOS chroot')
        sys.exit(1)

    with open(user_conf, 'r') as f:
        has_new_conf = False
        has_old_conf = False
        for line in f.read().split('\n'):
            if line == conf_line:
                has_new_conf = True
            if line == old_conf_line:
                has_old_conf = True

        if not has_new_conf:
            print(f'Add "{conf_line}" to {user_conf} and rerun.')
            print('')
        if has_old_conf:
            print(f'You have config from a previous version of this '
                  f'script in {user_conf}.')
            print(f'Remove the line "{old_conf_line}" and rerun.')
            print('')

        if not has_new_conf or has_old_conf:
            sys.exit(1)

    subprocess.run(
        ['sudo', 'mkdir', '-p', '/etc/binhost'],
        check=True)

def write_binhost(board, uri):
    if uri:
        data = f'PORTAGE_BINHOST="{uri}"'
    else:
        # Make sure to clear the file if there's no BINHOST found.
        data = ''

    subprocess.run(
        ['sudo', 'tee', f'/etc/binhost/{board}'],
        input=data.encode(), stdout=subprocess.DEVNULL, check=True)

def is_internal():
    url = subprocess.run(
        ['git', 'config', '--get', 'remote.origin.url'],
        stdout=subprocess.PIPE,
        cwd='/mnt/host/source/.repo/manifests/',
        check=True).stdout.decode().strip()

    if 'chrome-internal.googlesource.com/chromeos/manifest-internal' in url:
        return True

    if 'chromium.googlesource.com/chromiumos/manifest' in url:
        return False

    print(f'Unknown manifest source {url}')
    sys.exit(1)

def get_snapshot_hashes():
    # 48 snapshots = 24 hours
    commit_range = 'HEAD~48..HEAD'

    internal = subprocess.run(
        ['git', 'log', commit_range, '--format=%H'],
        stdout=subprocess.PIPE,
        cwd='/mnt/host/source/.repo/manifests/',
        check=True).stdout.decode().split()

    if not is_internal():
        return internal

    external = subprocess.run(
        ['git', 'log', commit_range,
         '--format=%(trailers:key=Cr-External-Snapshot'
         ',separator=,valueonly)'],
        stdout=subprocess.PIPE,
        cwd='/mnt/host/source/.repo/manifests/',
        check=True).stdout.decode().split()

    # Flatten the list of (internal, external) pairs. This gives us a
    # priority order where newer snapshots > older, and then internal
    # snapshots > external snapshots.
    return [rev for pair in zip(internal, external) for rev in pair]

def download_json(tmp, rev):
    subprocess.run(['gsutil', '-m', 'cp', '-r',
                    f'gs://chromeos-prebuilt/snapshot/{rev}',
                    tmp],
                   stderr=subprocess.DEVNULL)
    # Don't check the return code because gsutil returns non-zero if
    # some of the paths don't exist.

def parse_json(tmp, rev):
    result = []
    for curr, _, files in os.walk(tmp / rev):
        for f in files:
            with open(Path(curr) / f, 'r') as f:
                result.append(json.loads(f.read()))

    return result

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=f"""Find up-to-date binary package sources

Chrome OS tries to speed up builds by using binary packages taken from
CI builds. However, the configuration file that controls which build
these packages are taken from is itself a part of the git repo, which
means it is effectivly always out of date. See crbug.com/1073565 for
more details.

This script tries to solve this by looking up recent binary prebuilts
for all boards. This is most useful if you sync to the "stable"
manifest branch, which will always have up to date prebuilts. If you
haven't used this script before, you must add the line
    {conf_line}
to the file {user_conf} in your chroot.""")
    parser.add_argument(
        'board', nargs='?', default='', type=str,
        help='By default, we try to configure prebuilts for all '
        'available boards. This can be slow. If you only want to '
        'configure a single board, set this option.')
    parser.add_argument(
        'profile', nargs='?', default='base', type=str,
        help='Portage allows each board to have many profiles which '
        'can have different build options configured, and therefore '
        'require different prebuilts. This script can only configure '
        'a board to use prebuilts from one profile at a time. By '
        'default we use "base" for everything, and this is usually '
        'correct, but if you set up your sysroot by passing the '
        '"--profile" option to setup_board you will need to set this. '
        'Note that this is not persistent. If you run the default '
        'form of this command any binhosts you set with this '
        'will be overwritten.')
    parser.add_argument(
        '--progress', default=False, action='store_true',
        help='Show progress')

    args = parser.parse_args()

    run_prechecks()

    # Snapshot hashes are listed newest-to-oldest, so in descending
    # order of priority.
    revs = get_snapshot_hashes()

    # Files in /etc/binhost overwrite the normal BINHOST selection, so
    # we don't want to leave stale data in there ever. Make sure
    # binhost_map contains an entry for every file we manage. If we
    # didn't get any results, we will clear the file in write_binhost.
    #
    # If we're only querying a single builder, don't worry about
    # it. Not getting a result for a board doesn't mean that file is
    # stale.
    binhost_map = defaultdict(str)
    if not args.board:
        for path in os.listdir('/etc/binhost'):
            binhost_map[path] = ''
    else:
        binhost_map[args.board] = ''

    tmp = tempfile.TemporaryDirectory()
    tmp_path = Path(tmp.name)
    binhosts_found = 0
    for count, rev in enumerate(revs):
        if args.progress:
            print(f'\rChecking {count}/{len(revs)}', end='')
        download_json(tmp_path, rev)
        builds = parse_json(tmp_path, rev)

        for build in builds:
            if build['profile']['name'] != args.profile:
                continue

            if args.board and build['buildTarget']['name'] != args.board:
                continue

            # Higher priority build already found
            if binhost_map[build['buildTarget']['name']]:
                continue

            binhost_map[build['buildTarget']['name']] = build['location']
            binhosts_found += 1

        # if args.board is set, we only need to find one build.
        if args.board and binhosts_found:
            break

        # Rough estimate of the total number of boards
        if binhosts_found > 135:
            break
    if args.progress:
        print()
    for board, uri in binhost_map.items():
        write_binhost(board, uri)

    print(f'Found binhosts for {binhosts_found} boards')

if __name__ == '__main__':
    main()
