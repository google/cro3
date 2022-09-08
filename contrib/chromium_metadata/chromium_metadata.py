#!/usr/bin/env python3
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=missing-docstring

"""Creates Chromium Metadata files.

See https://source.chromium.org/chromium/infra/infra/+/HEAD:go/src/infra/tools/dirmd/README.md.
"""

import argparse
import logging
import os
import subprocess
import sys
import pathlib

from chromite.lib import cros_build_lib
from chromite.lib import gerrit
from chromite.lib import git

METADATA_FILE_NAME = 'DIR_METADATA'

METADATA_TEMPLATE = """\
# Metadata information for this directory.
#
# For more information on DIR_METADATA files, see:
#   https://source.chromium.org/chromium/infra/infra/+/HEAD:go/src/infra/tools/dirmd/README.md
#
# For the schema of this file, see Metadata message:
#   https://source.chromium.org/chromium/infra/infra/+/HEAD:go/src/infra/tools/dirmd/proto/dir_metadata.proto

buganizer {
  component_id: FIXME
}
buganizer_public {
  component_id: FIXME
}
team_email: "YOUR_TEAM@google.com"
"""

COMMIT_MSG_TEMPLATE = """
{COMPONENT}{DELIM}Add Chromium Metadata file

BUG=b:172930457
TEST=none
"""

GERRIT_COMMENT = """
This is an automated CL. Please replace the buganizer component (public  \
and private) and team email with the correct values. A team email is \
encouraged, but if there isn't one, you can remove that field.
"""

GERRIT_HASHTAG = '#chromium_metadata_b/172930457'


def find_git_dir():
    cmd = ['git', 'rev-parse', '--git-dir']
    ret = cros_build_lib.run(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    return ret.stdout.decode().strip()


def create_cl(git_repo, sub_dir, reviewers):
    branch = '172930457-' + sub_dir.as_posix().replace('.', '')
    if git.MatchBranchName(git_repo.as_posix(), branch):
        logging.debug('branch already exists; skipping')
        return

    remote = git.GetTrackingBranchViaManifest(git_repo, for_push=True)

    git.CreateBranch(git_repo=git_repo,
                     branch=branch,
                     branch_point=remote.ref)

    metadata_file_path = os.path.join(git_repo, sub_dir, METADATA_FILE_NAME)
    with open(metadata_file_path, 'w') as f:
        f.write(METADATA_TEMPLATE)

    git.AddPath(metadata_file_path)

    delim = ': '
    if sub_dir == pathlib.Path('.'):
        sub_dir = ''
        delim = ''

    commit_msg = COMMIT_MSG_TEMPLATE.format(COMPONENT=sub_dir, DELIM=delim)
    git.Commit(git_repo, commit_msg)
    upload = input(
        f'Would you like to upload {metadata_file_path}? [y/n]')
    if upload == 'y':
        git.UploadCL(git_repo=git_repo, remote=remote.remote,
                     branch=remote.ref.split('/')[-1],
                     reviewers=reviewers)

        git_rev = git.GetGitRepoRevision(git_repo)
        gerrit_helper = gerrit.GetGerritHelper(remote=remote.remote)
        gerrit_patch = gerrit_helper.QuerySingleRecord(git_rev)
        gerrit_helper.SetReview(gerrit_patch, GERRIT_COMMENT)
        gerrit_helper.SetHashtags(gerrit_patch, add=[GERRIT_HASHTAG], remove=[])


def extract_owners(owners_file: pathlib.Path):
    owners = []
    with open(owners_file) as f:
        for line in f.readlines():
            line = line.strip()
            if line and (not line.startswith('#')
                         and not line.startswith('include')
                         and not line.startswith('*')):
                owners.append(line)

    return owners


def find_owners_files(git_repo):
    logging.debug('searching %s', git_repo)
    files = []
    for f in pathlib.Path(git_repo).rglob('OWNERS'):
        files.append(f)
    return files


def create_metadata_files(root_dir: pathlib.Path):
    owners_files = find_owners_files(root_dir)
    for file_path in owners_files:
        if os.path.exists(file_path.joinpath(METADATA_FILE_NAME)):
            logging.debug('skipping existing file: %s', file_path)
            continue
        logging.debug('file_path: %s', file_path)
        owners = extract_owners(file_path)
        dir_name = file_path.parent.relative_to(root_dir)
        create_cl(sub_dir=dir_name, git_repo=root_dir, reviewers=owners)


def chromium_metadata():
    try:
        git_dir = find_git_dir()
        logging.debug(git_dir)
        git_repo = git.GetGitGitdir(git_dir)
        create_metadata_files(pathlib.Path(git_repo).parent)
    except cros_build_lib.RunCommandError:
        logging.error('Must be run in a git repo.')
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()

    log_level_choices = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    parser.add_argument(
        '--log_level', '-l',
        choices=log_level_choices,
        default='INFO'
    )

    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)

    chromium_metadata()

    return 0


if __name__ == '__main__':
    sys.exit(main())
