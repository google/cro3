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
        ['bb', 'ls', '-json', '-fields', 'input,output',
         '-predicate', query_str],
        stdout=subprocess.PIPE,
        check=True).stdout.decode()

def parse_response(bb_ret):
    # bb unhelpfully returns a bunch on concatenated JSON objects,
    # rather then a single top-level list, so we need to have our own
    # parsing loop rather then just doing json.loads().

    decoder = json.JSONDecoder()
    ret = []
    while True:
        try:
            obj, idx = decoder.raw_decode(bb_ret)
            ret.append(obj)
            bb_ret = bb_ret[idx:].strip()
        except json.decoder.JSONDecodeError:
            return ret

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=f"""Find up-to-date binary package sources

Chrome OS tries to speed up builds by using binary packages taken from
CI builds. However, the configuration file that controls which build
these packages are taken from is itself a part of the git repo, which
means it is effectivly always out of date. See crbug.com/1073565 for
more details.

This script tries to solve this by looking up CI builds which match
the currently checked out manifest snapshot. Only exact matches are
used, so this is most useful if you sync to the "stable" manifest
branch. If you haven't used this script before, you must add the line
    {conf_line}
to the file {user_conf} in your chroot. This script also
relies on the buildbucket CLI tool. If you haven't previously used it,
you will need to run "bb auth-login".""")
    parser.add_argument(
        'builder', nargs='?', default='', type=str,
        help='By default, we try to make use of all builders. '
        'However, for some boards, such as amd64-generic, there '
        'are multiple builders with different profiles. By '
        'default we assume the one named {board}-postsubmit is '
        'the desired builder, if one exists, or the first '
        'result otherwise, but if you have configured your '
        'build with "setup_board --profile" or similar you may '
        'need to set this option to a different builder. Note '
        'that this is not persistent. If you run the default '
        'form of this command any binhosts you set with this '
        'will be overwritten.')

    args = parser.parse_args()

    run_prechecks()

    query = {
        'builder': {
            'project': 'chromeos',
            'bucket': 'postsubmit',
        },

        'tags': [{
            'key': 'snapshot',
            'value': get_current_snapshot(),
        }],

        'status': 'SUCCESS',
    }

    if args.builder:
        query['builder']['builder'] = args.builder

    bb_ret = run_query(query)

    # Some postsubmit builders use the external manifest, so if we
    # just used the internal manifest try the external one too to get
    # more builders.
    if is_internal():
        query['tags'][0]['value'] = (
            internal_to_external_snapshot(query['tags'][0]['value']))
        bb_ret += run_query(query)

    bb_ret = parse_response(bb_ret)
    if not bb_ret:
        print('Warning: buildbucket returned no builds.')

    binhost_map = defaultdict(str)

    # Files in /etc/binhost overwrite the normal BINHOST selection, so
    # we don't want to leave stale data in there ever. Make sure
    # binhost_map contains an entry for every file we manage. If we
    # didn't get any results, we will clear the file in write_binhost.
    #
    # If we're only querying a single builder, don't worry about
    # it. Not getting a result for a board doesn't mean that file is
    # stale.
    if not args.builder:
        for path in os.listdir('/etc/binhost'):
            binhost_map[path] = ''

    for build in bb_ret:
        if 'build_target' not in build['input']['properties']:
            # The postsubmit-orchestrator task, skip
            continue
        if 'prebuilts_uri' not in build['output']['properties']:
            # Some builders don't create prebuilts, skip
            continue

        name = build['builder']['builder']
        board = build['input']['properties']['build_target']['name']
        uri = build['output']['properties']['prebuilts_uri']
        if not binhost_map[board] or name == f'{board}-postsubmit':
            binhost_map[board] = uri

    for board,uri in binhost_map.items():
        write_binhost(board, uri)

    binhosts_found = len([i for i in binhost_map.values() if i])
    print(f'Found binhosts for {binhosts_found} boards')

if __name__ == '__main__':
    main()
