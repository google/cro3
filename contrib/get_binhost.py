#!/usr/bin/env python3
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import subprocess
import sys

from chromite.lib.cros_build_lib import IsInsideChroot

user_conf = '/etc/make.conf.user'
conf_line = 'source ${ROOT}/etc/make.conf.binhost'

def run_prechecks():
    if not IsInsideChroot():
        print('This script must be run inside the CrOS chroot')
        sys.exit(1)

    with open(user_conf, 'r') as f:
        for line in f.read().split('\n'):
            if line == conf_line:
                break
        else:
            print(f'Add "{conf_line}" to {user_conf} and rerun')
            sys.exit(1)

def write_binhost(board, s):
    subprocess.run(
        ['sudo', 'tee', f'/build/{board}/etc/make.conf.binhost'],
        input=s.encode(), check=True)

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

def get_current_snapshot():
    return subprocess.run(
        ['git', 'rev-parse', 'HEAD'],
        stdout=subprocess.PIPE,
        cwd='/mnt/host/source/.repo/manifests/',
        check=True).stdout.decode().strip()

def internal_to_external_snapshot(rev):
    return subprocess.run(
        ['git', 'footers', '--key', 'Cr-External-Snapshot', rev],
        stdout=subprocess.PIPE,
        cwd='/mnt/host/source/.repo/manifests/',
        check=True).stdout.decode().strip()

def run_query(query):
    query_str = json.dumps(query)

    return subprocess.run(
        ['bb', 'ls', '-json', '-fields', 'output', '-predicate', query_str],
        stdout=subprocess.PIPE,
        check=True).stdout.decode()

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=f"""Find up-to-date binary package sources

Chrome OS tries to speed up builds by using binary packages taken from
CI builds. However, the configuration file that controls which build
these packages are taken from is itself a part of the git repo, which
means it is effectivly always out of date. See crbug.com/1073565 for
more details.

This script tries to solve this by looking up a CI build which matches
the currently checked out manifest snapshot. Only exact matches are
used, so this is most useful if you sync to the "stable" manifest
branch. If you haven't used this script before, you must add the line
    {conf_line}
to the file {user_conf} in your chroot. This script also
relies on the buildbucket CLI tool. If you haven't previously used it,
you will need to run "bb auth-login".""")
    parser.add_argument('board', type=str, help='The board to configure')

    args = parser.parse_args()

    run_prechecks()

    query = {
        'builder': {
            'project': 'chromeos',
            'bucket': 'postsubmit',
            'builder': f'{args.board}-postsubmit',
        },

        'tags': [{
            'key': 'snapshot',
            'value': get_current_snapshot(),
        }],

        'status': 'SUCCESS',
    }

    bb_ret = run_query(query)

    # Some postsubmit builders use the external manifest, so if we
    # didn't find anything and we were using the internal manifest,
    # try using the external one instead.
    if not bb_ret.strip() and is_internal():
        query['tags'][0]['value'] = (
            internal_to_external_snapshot(query['tags'][0]['value']))
        bb_ret = run_query(query)

    # If we still didn't find anything, give up.
    if not bb_ret.strip():
        print('Failed to find an exact postsubmit match')

        # Clear the config file so builds will fallback to the
        # PORTAGE_BINHOST it would normally use.
        write_binhost(args.board, '')
        sys.exit(1)

    bb_ret = json.loads(bb_ret)
    uri = bb_ret['output']['properties']['prebuilts_uri']
    write_binhost(args.board, f'PORTAGE_BINHOST={uri}\n')

if __name__ == '__main__':
    main()
