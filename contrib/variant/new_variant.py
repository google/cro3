#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
"""Create a new variant of an existing reference board

This program will call all of the scripts that create the various pieces
of a new variant. For example to create a new variant of the hatch base
board, the following scripts are called:

* platform/dev/contrib/variant/create_coreboot_variant.sh
* platform/dev/contrib/variant/create_coreboot_config.sh
* platform/dev/contrib/variant/create_depthcharge_config.sh
* private-overlays/baseboard-hatch-private/sys-boot/
 * coreboot-private-files-hatch/files/add_fitimage.sh
 * coreboot-private-files-hatch/asset_generation/gen_fit_image.sh
  * Outside the chroot, because it uses WINE to run the FIT tools
* platform/dev/contrib/variant/create_initial_ec_image.sh
* platform/dev/contrib/variant/add_variant_to_yaml.sh
* private-overlays/overlay-hatch-private/chromeos-base/
 * chromeos-config-bsp-hatch-private/add_variant.sh

Once the scripts are done, the following repos have changes

* third_party/coreboot
* third_party/chromiumos-overlay
* private-overlays/baseboard-hatch-private
* platform/depthcharge
* platform/ec
* private-overlays/overlay-hatch-private
* overlays

The program has support for multiple reference boards, so the repos,
directories, and scripts above can change depending on what the reference
board is.
"""

from __future__ import print_function
import argparse
import importlib
import json
import logging
import os
import subprocess
import sys
from chromite.lib import build_target_lib
from chromite.lib import cros_build_lib
from chromite.lib import git
from chromite.lib import gerrit
from chromite.lib import osutils
from chromite.lib import workon_helper
import requests
import step_names
import variant_status


def main():
    """Create a new variant of an existing reference board

    This program automates the creation of a new variant of an existing
    reference board by calling various scripts that copy the reference board,
    modify files for the new variant, stage commits, and upload to gerrit.

    Note that one of the following is required:
    * --continue
    * --board=BOARD --variant=VARIANT [--bug=BUG]
    """
    board, variant, bug, branch, continue_flag, abort_flag = get_args()

    if not check_flags(board, variant, bug, continue_flag, abort_flag):
        return False

    status = get_status(board, variant, bug, branch, continue_flag, abort_flag)
    if status is None:
        return False

    status.load()

    # Where is new_variant.py located?
    status.my_loc = os.path.dirname(os.path.abspath(__file__))

    # If the user specified --abort, override the current step.
    if abort_flag:
        status.step = step_names.ABORT

    while status.step is not None:
        status.save()
        if not perform_step(status):
            logging.debug('perform_step %s returned False; exiting ...',
                          status.step)
            return False

        move_to_next_step(status)

    return True


def get_args():
    """Parse the command-line arguments

    There doesn't appear to be a way to specify that --continue is
    mutually exclusive with --board, --variant, and --bug. As a result,
    all arguments are optional, and another function will apply the logic
    to check if there is an illegal combination of arguments.

    Returns a list of:
        board             Name of the reference board
        variant           Name of the variant being created
        bug               Text for bug number, if any ('None' otherwise)
        continue_flag     Flag if --continue was specified
    """
    parser = argparse.ArgumentParser(
        description=main.__doc__,
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--board', type=str, help='Name of the reference board')
    parser.add_argument(
        '--variant', type=str, help='Name of the new variant to create')
    parser.add_argument(
        '--bug', type=str, help='Bug number to reference in commits')
    parser.add_argument(
        '--branch', type=str, help='Value for BRANCH= in commit messages')
    # Use a group so that we can enforce mutually-exclusive arguments.
    # argparse does not support nesting groups, so we can't put board,
    # variant, and bug into a group and have that group as another mutually
    # exclusive option.
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--continue', action='store_true',
        dest='continue_flag', help='Continue the process from where it paused')
    group.add_argument(
        '--abort', action='store_true',
        dest='abort_flag', help='Cancel the process and abandon all commits')
    parser.add_argument(
        '--verbose', action='store_true',
        dest='verbose_flag', help='Enable verbose output of progress')
    args = parser.parse_args()

    if args.verbose_flag:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    board = args.board
    if board is not None:
        board = board.lower()

    variant = args.variant
    if variant is not None:
        variant = variant.lower()

    bug = args.bug or 'None'
    branch = args.branch or 'None'

    return (board, variant, bug, branch, args.continue_flag, args.abort_flag)


def check_flags(board, variant, bug, continue_flag, abort_flag):
    """Check the flags to ensure no invalid combinations

    We allow any of the following:
    --abort
    --continue
    --board=board_name --variant=variant_name
    --board=board_name --variant=variant_name --bug=bug_text

    The argument parser does have the functionality to represent the
    combination of --board and --variant as a single mutually-exclusive
    argument, so we have to use this function to do the checking.

    Args:
        board: Name of the reference board
        variant: Name of the variant being created
        bug: Text for bug number, if any ('None' otherwise)
        continue_flag: Flag if --continue was specified
        abort_flag: Flag if --abort was specified

    Returns:
        True if the arguments are acceptable, False otherwise
    """
    # If either --abort or --continue is set, then disallow any of the
    # board name, variant name, or bug number to be set.
    if continue_flag or abort_flag:
        if board is not None or variant is not None or bug != 'None':
            logging.error('Do not use --board, --variant, or --bug with '
                          '--continue or --abort')
            return False
        return True

    # At this point, neither --continue nor --abort are set, so we must have
    # both --board and --variant values.
    if board is None or variant is None:
        logging.error('Both --board and --variant must be specified')
        return False

    return True


def get_status(board, variant, bug, branch, continue_flag, abort_flag):
    """Create the status file or get the previous status

    This program can stop at several places as we have to wait for CLs
    to work through CQ or be upstreamed into the chromiumos tree, so just
    like a git cherry-pick, there is a --continue option to pick up where
    you left off by reading a specially-named status file.

    If --continue is specified, the status file must exist.
    If the status file exists, then --continue must be specified.
    When --continue is specified, we read the status file and return
    with the contents.

    If the status file does not exist, we will create the state file with
    the board, variant, and (optional) bug details.

    To decouple the list of boards supported from this main program, we
    try to import a module with the same name as the reference board,
    so --board=hatch means that we import hatch.py. If we can't import
    the file, then we don't support that reference board.

    The board-specific module will set several variables, which we will
    copy into the object that we return.

    * base - the name of the base board, such as Hatch, Volteer, or Zork.
        This can be different from the reference board, e.g. the Trembyle
        reference board in the Zork project.
    * coreboot_base - the name of the base board in coreboot. Usually the same
        as base, but can differ, e.g. for Puff, the base is Puff, but the
        coreboot_base is Hatch because Puff is based on Hatch.
    * coreboot_dir - base directory for coreboot, usually third_party/coreboot
        but could differ for processors that use a private repo
    * coreboot_reference - the name of the reference board that we're using to
        make the variant. This can be different from base (e.g. Ambassador is
        its own board, but uses Puff as a coreboot reference).
    * cb_config_dir - base directory for coreboot configs, usually
        third_party/chromiumos-overlay/sys-boot/coreboot/files/configs but
        could differ for processors that use a private repo
    * depthcharge_dir - base directory for depthcharge, usually
        platform/depthcharge
    * step_list - list of steps (named in step_names.py) to run in sequence
        to create the new variant of the reference board
    * ec_board - EC board to use as a reference. Defaults to the value of
        board but can be different, e.g. brya0 specifies 'brya'
    * fsp - package name for FSP. This may be None, depending on the
        processor on the reference board
    * fitimage_pkg - package name for the fitimage
    * fitimage_dir - base directory for fitimage; prepend
        '/mnt/host/source/src/' in chroot, prepend '~/chromiumos/src' outside
        the chroot
    * fitimage_bin_dir - directory under fitimage_dir where the fitimage
        binary will be
    * fitimage_versions_dir - directory under fitimage_dir where the fitimage
        versions file will be, defaults to the value of fitimage_bin_dir
    * fitimage_bin - name of the fitimage binary to format with the variant
        name, default of `fitimage-%s.bin`
    * fitimage_cmd - explanation of gen_fit_image command, i.e. tell the user
        how to run gen_fit_image.sh
    * fitimage_script - script to add fitimage sources, defaults
        to 'files/add_fitimage.sh' if not present. Only volteer and volteer2
        currently need to use this.
    * workon_pkgs - list of packages to cros_workon
    * emerge_cmd - the emerge command, e.g. 'emerge-hatch'
    * emerge_pkgs - list of packages to emerge
    * config_workon_pkgs - list of packages to cros_workon to build the
        project config
    * config_emerge_pkgs - list of packages to emerge to build the project
        config
    * private_yaml_dir - directory for the private yaml file
    * commits - map of commits for the various steps. Indexed by step name,
        and the step names used are the same ones in step_names.py
    * repo_upload_list - list of commits to upload using `repo upload`
    * coreboot_push_list - list of commits to upload using `git push` to
        coreboot
    * depends - maps a step to a list of steps on which it depends, e.g.
        depends[step_names.ADD_PRIV_YAML] is a list of other steps that
        the 'add_priv_yaml' step depends on. This map is used to amend
        the commits with CL numbers for Cq-Depend.

    Additionally, the following fields will be set:

    * board - the name of the reference board, e.g. 'hatch'. The --board
        command line flag specifies this value, and new_variant derives the
        the name of the python module to load from this value. However, in
        certain cases (volteer2), the python module may override this value
    * variant - the name of the variant, e.g. 'sushi'
    * bug - optional text for a bug ID, used in the git commit messages.
        Could be 'None' (as text, not the python None), or something like
        'b:12345' for buganizer, or 'chromium:12345'
    * branch - optional text for a BRANCH= value in the commit message for
        repos that use the BRANCH field (coreboot and EC). If not specified,
        then None.
    * step - internal state tracking, what step of the variant creation
        we are at.
    * yaml_file - internal, just the name of the file where all this data
        gets saved.
    * commit - a map of maps that tracks all of the git commit and gerrit CL
        data for each of the steps in the process. For example,
        status.commit['add_priv_yaml'] is a map that has all the information
        about the 'add_priv_yaml' step. The keys in the maps allow us to
        determine where the commit is, the change_id, if it has been uploaded
        to gerrit and where.

            branch_name - the name of the git branch
            change_id - the change-id assigned by the commit hook. Gerrit
                uses the change_id to track new patchsets in the CL
            dir - the directory where the commit has been created
            gerrit - the name of the gerrit instance to which the CL has
                been uploaded, one of 'chromium', 'chrome-internal', or
                'coreboot'
            cl_number - the CL number on the gerrit instance

        When the commit is created, branch_name, change_id, and dir are all
        set. The gerrit and cl_number keys are not set until the CL has been
        uploaded to a gerrit instance.

    These data might come from the status file (because we read it), or
    they might be the initial values after we created the file (because
    it did not already exist).

    Args:
        board: Name of the reference board
        variant: Name of the variant being created
        bug: Text for bug number, if any ('None' otherwise)
        branch: Text for a BRANCH= value in the commit message (or 'None')
        continue_flag: Flag if --continue was specified
        abort_flag: Flag if --abort was specified

    Returns:
        variant_status object with all the data mentioned above
    """
    status = variant_status.variant_status()
    if continue_flag or abort_flag:
        if status.yaml_file_exists():
            return status

        if continue_flag:
            op = '--continue'
        if abort_flag:
            op = '--abort'
        logging.error('%s does not exist; cannot %s', status.yaml_file, op)
        return None

    # If we get here, the user provided --board and --variant (because
    # check_flags() returned Trued), but the yaml file already exists,
    # so we print an error message and bail.
    if status.yaml_file_exists():
        logging.error(
            'new_variant already in progress; did you forget --continue?')
        return None

    # At this point, it's not --continue, not --abort, the yaml file doesn't
    # exist, and we have valid values for --board, --variant, and --bug (bug
    # might be the default value of "None"). Create the yaml file with data
    # from the reference board's loadable module.
    status.board = board
    status.variant = variant
    status.bug = bug
    status.branch = branch

    # Load the appropriate module and copy all the data from it.
    try:
        module = importlib.import_module(board)
    except ImportError:
        print('Unsupported board "' + board + '"')
        sys.exit(1)

    # Special case: allow the module to override the name of the reference
    # board. Almost always, you want the module name (e.g. puff.py) and the
    # name of the reference board (e.g. puff) to match. However, for some
    # boards (volteer2), you want to have the reference board name still
    # be 'volteer'.
    status.board                = getattr(module, 'board', status.board)

    status.base                 = module.base
    status.coreboot_base        = getattr(module, 'coreboot_base', module.base)
    status.coreboot_dir         = module.coreboot_dir
    status.coreboot_reference   = getattr(module, 'coreboot_reference',
                                          status.board)
    status.cb_config_dir        = getattr(module, 'cb_config_dir', None)
    status.depthcharge_dir      = getattr(module, 'depthcharge_base',
                                          'platform/depthcharge')
    status.depthcharge_base     = getattr(module, 'depthcharge_base',
                                          status.coreboot_base)
    status.depthcharge_ref      = getattr(module, 'depthcharge_ref',
                                          status.coreboot_base)
    status.ec_board             = getattr(module, 'ec_board', status.board)
    status.emerge_cmd           = module.emerge_cmd
    status.emerge_pkgs          = module.emerge_pkgs
    status.fitimage_bin         = getattr(module, 'fitimage_bin',
                                          'fitimage-%s.bin')
    status.fitimage_dir         = getattr(module, 'fitimage_dir', None)
    status.fitimage_bin_dir     = getattr(module, 'fitimage_bin_dir', None)
    status.fitimage_versions_dir= getattr(module, 'fitimage_versions_dir',
                                          status.fitimage_bin_dir)
    status.fitimage_versions    = getattr(module, 'fitimage_versions',
                                          'fitimage-%s-versions.txt')
    status.fitimage_pkg         = getattr(module, 'fitimage_pkg', None)
    status.fitimage_cmd         = getattr(module, 'fitimage_cmd', None)
    status.fitimage_script      = getattr(module, 'fitimage_script',
                                          'files/add_fitimage.sh')
    status.fsp                  = getattr(module, 'fsp', None)
    status.private_yaml_dir     = getattr(module, 'private_yaml_dir', None)
    status.step_list            = module.step_list
    status.workon_pkgs          = module.workon_pkgs
    status.config_workon_pkgs   = module.config_workon_pkgs
    status.config_emerge_pkgs   = module.config_emerge_pkgs
    status.coreboot_push_list   = module.coreboot_push_list
    status.repo_upload_list     = module.repo_upload_list
    status.depends              = module.depends

    # Start at the first entry in the step list
    status.step = status.step_list[0]

    # Start an empty map for tracking CL data
    status.commits = {}

    status.save()

    return status


def perform_step(status):
    """Call the appropriate function for the current step

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the step succeeded, False if it failed
    """
    # Function to call based on the step
    dispatch = {
        step_names.PROJECT_CONFIG:  project_config,
        step_names.FW_BUILD_CONFIG: fw_build_config,
        step_names.CB_VARIANT:      create_coreboot_variant,
        step_names.CB_CONFIG:       create_coreboot_config,
        step_names.DC_VARIANT:      create_depthcharge_variant,
        step_names.CRAS_CONFIG:     copy_cras_config,
        step_names.ADD_FIT:         add_fitimage,
        step_names.GEN_FIT:         gen_fit_image_outside_chroot,
        step_names.COMMIT_FIT:      commit_fitimage,
        step_names.EC_IMAGE:        create_initial_ec_image,
        step_names.EC_BUILDALL:     ec_buildall,
        step_names.ADD_PUB_YAML:    add_variant_to_public_yaml,
        step_names.ADD_PRIV_YAML:   add_variant_to_private_yaml,
        step_names.BUILD_CONFIG:    build_config,
        step_names.EMERGE:          emerge_all,
        step_names.PUSH:            push_coreboot,
        step_names.UPLOAD:          upload_CLs,
        step_names.FIND:            find_coreboot_upstream,
        step_names.CALC_CQ_DEPEND:  calc_cq_depend,
        step_names.ADD_CQ_DEPEND:   add_cq_depend,
        step_names.RE_UPLOAD:       re_upload,
        step_names.CLEAN_UP:        clean_up,
        step_names.ABORT:           abort,
    }

    if status.step not in dispatch:
        logging.error('Unknown step "%s", aborting...', status.step)
        sys.exit(1)

    return dispatch[status.step](status)


def move_to_next_step(status):
    """Move to the next step in the list

    Args:
        status: variant_status object tracking our board, variant, etc.
    """
    # Special case: the next step after 'abort' is 'clean_up'. Always.
    if status.step == step_names.ABORT:
        status.step = step_names.CLEAN_UP
        return

    if status.step not in status.step_list:
        logging.error('Unknown step "%s", aborting...', status.step)
        sys.exit(1)

    idx = status.step_list.index(status.step)
    if idx == len(status.step_list)-1:
        status.step = None
    else:
        status.step = status.step_list[idx+1]


def run_process(args, cwd=None, env=None, capture_output=False):
    """Run a process, log debug messages, return text output of process

    The capture_output parameter allows us to capture the output when we
    care about it (and not sending it to the screen), or ignoring it when
    we don't care, and letting the user see the output so they know that
    the build is still running, etc.

    Args:
        args: List of the command and its params
        cwd: If not None, cd to this directory before running
        env: Environment to use for execution; if needed, get os.environ.copy()
            and add variables. If None, just use the current environment
        capture_output: True if we should capture the stdout, false if we
            just care about success or not.

    Returns:
        If capture_output == True, we return the text output from running
        the subprocess as a list of lines, or None if the process failed.
        If capture_output == False, we return a True if it successed, or
        None if the process failed.

        The caller can evaluate as a bool, because bool(None) == False, and
        bool() of a non-empty list is True, or the caller can use the returned
        text for further processing.
    """
    logging.debug('Run %s', str(args))
    if cwd is not None:
        logging.debug('cwd = %s', cwd)
    try:
        if capture_output:
            output = subprocess.run(args, cwd=cwd, env=env, check=True,
                stderr=subprocess.STDOUT, stdout=subprocess.PIPE).stdout
        else:
            subprocess.run(args, cwd=cwd, env=env, check=True)
            # Just something to decode so we don't get an empty list
            output = b'True'

        logging.debug('process returns 0')
        # Convert from byte string to ASCII
        decoded = output.decode('utf-8')
        # Split into array of individual lines
        lines = decoded.split('\n')
        return lines
    except subprocess.CalledProcessError as err:
        logging.debug('process returns %s', str(err.returncode))
        return None


def get_git_commit_data(cwd):
    """Get the branch name and change id of the current commit

    Args:
        cwd: The current working directory, where we want to get the branch
            name and change id

    Returns:
        Map with 'dir', 'branch_name' and 'change_id' keys. The 'dir'
        key maps to the value of os.path.expanduser(cwd)
    """
    cwd = git.FindGitTopLevel(os.path.expanduser(cwd))
    logging.debug('get_git_commit_data(%s)', cwd)

    branch_name = git.GetCurrentBranch(cwd)
    if branch_name is None:
        logging.error('Cannot determine git branch name in %s; exiting', cwd)
        sys.exit(1)
    logging.debug('git current branch is %s', branch_name)

    change_id = git.GetChangeId(cwd)
    if change_id is None:
        logging.error('Cannot determine Change-Id in %s; exiting', cwd)
        sys.exit(1)
    logging.debug('git Change-Id is %s', change_id)

    return {
        'dir': cwd,
        'branch_name': branch_name,
        'change_id': change_id
    }


def change_id_to_sha(git_repo, change_id):
    """Find the SHA for a given Change-Id.

    Args:
        git_repo: Directory of git repository.
        change_id: The Change-Id to search for.

    Returns:
        The SHA hash for the Change-Id if only one commit is found.
        None if the Change-Id was not found.
        Raises a ValueError if more than one commit is found with the
        same Change-Id.
    """
    output = git.Log(git_repo, max_count=1, format='format:%H',
                     grep=fr'^Change-Id: {change_id}$')
    sha_hashes = output.splitlines()
    if not sha_hashes:
        return None
    if len(sha_hashes) > 1:
        raise ValueError('More than one SHA with that Change-Id found')
    return sha_hashes[0]


def get_commit_msg(git_repo, rev):
    """Get the commit message for a given revision.

    Because git.Log doesn't allow specifying check=False or getting the
    returncode, we have to catch the CalledProcessError instead.

    Args:
        git_repo: Directory of git repository.
        rev: The revision to search for, a SHA or a label.

    Returns:
        The commit message as a list of strings, if the revision exists.
        None if the revision was not found.
    """
    try:
        msg = git.Log(git_repo, max_count=1, format='format:%B', rev=rev)
        return msg.splitlines()
    except cros_build_lib.CalledProcessError as err:
        raise ValueError('SHA was not found') from err


def emerge_with_workon(status, workon_pkgs, emerge_cmd, emerge_pkgs, env=None):
    """Emerge a list of packages after `cros_workon start`ing them

    This function will `cros_workon start` a list of packages, then `emerge`
    another list of packages, and finally, `cros_workon stop` only those
    packages that were actually started by the `cros_workon start` command.
    Any package already in a `cros_workon start` state prior to this function
    will still be in that state when this function exits.

    To determine which packages this program started and which ones were
    already started, we query the list of packages being worked on, then
    cros_workon start the entire list (which will produce a "package already
    being worked on" type of message for anything already started), and then
    query the list of packages being worked on again. The difference between
    the before and after lists are the packages that this program started,
    and so that's the list of packages to cros_workon stop after the emerge
    is done.

    Args:
        status: variant_status object tracking our board, variant, etc.
        workon_pkgs: list of packages to `cros_workon start`
        emerge_cmd: the emerge command to run, e.g. 'emerge-volteer'
        emerge_pkgs: list of packages to `emerge`
        env: environment to pass to run_process, or None to pass default

    Returns:
        True if everything succeeded, False if something failed
    """
    # Get the list of packages that are already cros_workon started.
    build_target = build_target_lib.BuildTarget(status.base)
    workon = workon_helper.WorkonHelper(build_target.root, build_target.name)
    before_workon = workon.ListAtoms()

    # Only cros_workon start if the list is non-empty
    if workon_pkgs:
        workon.StartWorkingOnPackages(workon_pkgs)

    # Determine which packages we need to cros_workon stop.
    after_workon = workon.ListAtoms()
    stop_packages = list(set(after_workon) - set(before_workon))

    # Run the emerge command.
    emerge_result = run_process([emerge_cmd] + emerge_pkgs, env=env)

    # If the list is non-empty, cros_workon stop before returning the result.
    if stop_packages:
        workon.StopWorkingOnPackages(stop_packages)

    return emerge_result


def project_config(status):
    """Check if the project config is correct and complete

    For programs that use the new project/config structure with starlark
    configuration files, this function will check that emerging the
    project's configuration will result in a project-config.json that
    includes the new name of the new hwdesign (a.k.a. "variant").

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if everything succeeded, False if something failed
    """
    logging.info('Running step project_config')
    try:
        if not emerge_with_workon(status, status.config_workon_pkgs,
                                  status.emerge_cmd, status.config_emerge_pkgs):
            raise RuntimeError('Building the configuration failed.')

        # Make sure project-config.json exists in the /build tree
        emerged_json = os.path.join(
            '/build',
            status.base,
            'usr/share/chromeos-config/yaml/project-config.json')
        if not os.path.isfile(emerged_json):
            raise RuntimeError(
                f'project-config.json {emerged_json} does not exist.')

        # Search the JSON for a config with the new variant's name
        with open(emerged_json, 'r') as fp:
            pc = json.load(fp)

        names = {config['name'] for config in pc['chromeos']['configs']}
        if status.variant not in names:
            raise RuntimeError(
                f'variant name {status.variant} not found in {emerged_json}')

    except RuntimeError as e:
        logging.error(str(e))
        logging.error('Please file a bug in ChromeOS > Infra'
                      ' to have the project configuration updated.')
        logging.error('(go/cros-boxster-bug or '
                      'https://b.corp.google.com/issues/new?'
                      'component=167276&template=1022133)')
        return False

    return True


def fw_build_config(status):
    """Add the _FW_BUILD_CONFIG setting to the project config

    For programs that use the new project/config structure with starlark
    configuration files, this function calls fw_build_config.sh, which will
    modify the config.star file to have a default _FW_BUILD_CONFIG entry.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if everything succeeded, False if something failed
    """
    logging.info('Running step fw_build_config')
    fw_build_config_sh = os.path.join(status.my_loc, 'fw_build_config.sh')
    rc = run_process(
        [fw_build_config_sh,
        status.base,
        status.variant,
        status.bug])
    if rc:
        status.commits[step_names.FW_BUILD_CONFIG] = get_git_commit_data(
            os.path.join('/mnt/host/source/src/project',
                         status.base, status.variant))
    return rc


def create_coreboot_variant(status):
    """Create source files for a new variant of the reference board in coreboot

    This function calls create_coreboot_variant.sh to set up a new variant
    of the reference board.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if everything succeeded, False if something failed
    """
    logging.info('Running step create_coreboot_variant')
    cb_src_dir = os.path.join('/mnt/host/source/src/', status.coreboot_dir)
    environ = {**os.environ, 'CB_SRC_DIR': cb_src_dir,
               'NEW_VARIANT_BRANCH': status.branch}
    create_coreboot_variant_sh = os.path.join(status.my_loc,
        'create_coreboot_variant.sh')
    rc = run_process(
        [create_coreboot_variant_sh,
        status.coreboot_base,
        status.coreboot_reference,
        status.variant,
        status.bug], env=environ)
    if rc:
        status.commits[step_names.CB_VARIANT] = get_git_commit_data(cb_src_dir)
    return rc


def create_coreboot_config(status):
    """Create a coreboot configuration for a new variant

    This function calls create_coreboot_config.sh, which will make a copy
    of coreboot.${BOARD} into coreboot.${VARIANT}.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the script and test build succeeded, False if something failed
    """
    logging.info('Running step create_coreboot_config')
    # Only set CB_CONFIG_DIR if it's not None, so here we have to copy
    # the environment first and then optionally add a key.
    environ = os.environ.copy()
    if status.cb_config_dir is not None:
        environ['CB_CONFIG_DIR'] = status.cb_config_dir
    create_coreboot_config_sh = os.path.join(status.my_loc,
        'create_coreboot_config.sh')
    rc = run_process(
        [create_coreboot_config_sh,
        status.base,
        status.board,
        status.variant,
        status.bug], env=environ)
    if rc:
        # Use status.cb_config_dir if defined, or if not, use
        # '/mnt/host/source/src/third_party/chromiumos-overlay'
        cb_config_dir = os.path.join(
            '/mnt/host/source/src/',
            status.cb_config_dir or 'third_party/chromiumos-overlay')
        status.commits[step_names.CB_CONFIG] = get_git_commit_data(
            cb_config_dir)
    return rc


def create_depthcharge_variant(status):
    """Create source files for a new variant of the reference board in depthcharge

    This function calls create_depthcharge_variant.sh to set up a new variant
    of the reference board.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if everything succeeded, False if something failed
    """
    logging.info('Running step create_depthcharge_variant')
    dc_src_dir = os.path.join('/mnt/host/source/src/', status.depthcharge_dir)
    environ = {**os.environ, 'DC_SRC_DIR': dc_src_dir,
               'NEW_VARIANT_BRANCH': status.branch}
    create_depthcharge_variant_sh = os.path.join(status.my_loc,
        'create_depthcharge_variant.sh')
    rc = run_process(
        [create_depthcharge_variant_sh,
        status.depthcharge_base,        # base
        status.depthcharge_ref,         # reference
        status.variant,                 # variant
        status.bug], env=environ)
    if rc:
        status.commits[step_names.DC_VARIANT] = get_git_commit_data(dc_src_dir)
    return rc


def copy_cras_config(status):
    """Copy the cras config for a new variant

    This is only necessary for the Zork baseboard right now.
    This function calls copy_cras_config.sh, which will copy the
    cras config in overlays/overlay-${BASE}/chromeos-base/\
    chromeos-bsp-${BASE}/files/cras-config/${BASE} to .../${VARIANT}

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the script and test build succeeded, False if something failed
    """
    logging.info('Running step copy_cras_config')
    copy_cras_config_sh = os.path.join(status.my_loc, 'copy_cras_config.sh')
    rc = run_process(
        [copy_cras_config_sh,
        status.base,
        status.board,
        status.variant,
        status.bug])
    if rc:
        status.commits[step_names.CRAS_CONFIG] = get_git_commit_data(
            '/mnt/host/source/src/overlays')
    return rc


def add_fitimage(status):
    """Add the source files for a fitimage for the new variant

    This function calls add_fitimage.sh to create a new XSL file for the
    variant's fitimage, which can override settings from the reference board's
    XSL. When this is done, the user will have to build the fitimage by running
    gen_fit_image.sh outside of the chroot (and outside of this program's
    control) because gen_fit_image.sh uses WINE, which is not installed in
    the chroot. (There is a linux version of FIT, but it requires Open GL,
    which is also not installed in the chroot.)

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the script succeeded, False otherwise
    """
    logging.info('Running step add_fitimage')
    add_fitimage_sh = os.path.expanduser(os.path.join(
        '/mnt/host/source/src', status.fitimage_dir, status.fitimage_script))
    rc = run_process(
        [add_fitimage_sh,
        status.variant,
        status.bug])
    if rc:
        fitimage_dir = os.path.join('/mnt/host/source/src', status.fitimage_dir)
        status.commits[step_names.COMMIT_FIT] = get_git_commit_data(
            fitimage_dir)
    return rc


def gen_fit_image_outside_chroot(status):
    """Tell the user to run gen_fit_image.sh outside the chroot

    As noted for add_Fitimage(), gen_fit_image.sh cannot run inside the
    chroot. This function tells the user to run gen_fit_image.sh in
    their normal environment, and then come back (--continue) when that
    is done.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True
    """
    logging.info('Running step gen_fit_image_outside_chroot')
    fit_image_files = check_fit_image_files(status)
    # If the list is empty, then `not` of the list is True, so the files
    # we need are all present and we can continue.
    if not fit_image_files:
        return True

    logging.error('The following files need to be generated:')
    for filename in fit_image_files:
        logging.error('* %s', filename)
    logging.error(
        'The fitimage sources are ready for gen_fit_image.sh to process.')
    logging.error(
        'gen_fit_image.sh cannot run inside the chroot. Open a new terminal,')
    logging.error(
        'change to the directory where gen_fit_image.sh is located, and run')
    logging.error(status.fitimage_cmd, status.variant)
    logging.error('Then re-start this program with --continue.')
    logging.error(
        'If your chroot is based in ~/chromiumos, then the folder you want is')
    logging.error('~/chromiumos/src/%s/asset_generation', status.fitimage_dir)
    return False


def check_fit_image_files(status):
    """Check if the fitimage has been generated

    This function is not called directly as a step, and so it doesn't need
    to produce any error messages to the user (except with --verbose).
    gen_fit_image_outside_chroot will call this function to see if the
    fitimage files exist, and if not, then that function will print the
    message about how the user needs to run gen_fit_image.sh outside the
    chroot.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        List of files that *DO NOT* exist and need to be created, [] if
        all files are present.
    """
    fitimage_bin_dir = os.path.join('/mnt/host/source/src',
        status.fitimage_dir, status.fitimage_bin_dir)
    logging.debug('fitimage_bin_dir = "%s"', fitimage_bin_dir)
    fitimage_versions_dir = os.path.join('/mnt/host/source/src',
        status.fitimage_dir, status.fitimage_versions_dir)
    logging.debug('fitimage_versions_dir = "%s"', fitimage_versions_dir)

    files_not_found = []
    fitimage_bin = status.fitimage_bin % status.variant
    if not os.path.isfile(os.path.join(fitimage_bin_dir, fitimage_bin)):
        files_not_found.append(fitimage_bin)

    fitimage_versions_file = status.fitimage_versions % status.variant
    if not os.path.isfile(os.path.join(fitimage_versions_dir,
        fitimage_versions_file)):
        files_not_found.append(fitimage_versions_file)

    return files_not_found


def commit_fitimage(status):
    """Add the fitimage files to the git commit

    This function calls commit_fitimage.sh to move the fitimage binary and
    -versions files from asset_generation/outputs to files/ and then adds
    those files and fit.log to the existing git commit.
    Depending on the baseboard, there may be different file names (such
    as fit-${VARIANT}.log for volteer) and/or additional files (such as
    files/blobs/description-${VARIANT}.bin for volteer)

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the script succeeded, False if something failed
    """
    logging.info('Running step commit_fitimage')
    commit_fitimage_sh = os.path.expanduser(os.path.join(
        '/mnt/host/source/src', status.fitimage_dir,
        'files/commit_fitimage.sh'))
    return run_process([commit_fitimage_sh, status.variant])


def create_initial_ec_image(status):
    """Create an EC image for the variant as a clone of the reference board

    This function calls create_initial_ec_image.sh, which will clone the
    reference board to create the variant. The shell script will build the
    EC code for the variant.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the script and test build succeeded, False if something failed
    """
    logging.info('Running step create_initial_ec_image')
    environ = {**os.environ, 'NEW_VARIANT_BRANCH': status.branch}
    create_initial_ec_image_sh = os.path.join(status.my_loc,
        'create_initial_ec_image.sh')
    if not run_process(
        [create_initial_ec_image_sh,
        status.ec_board,
        status.variant,
        status.bug], env=environ):
        return False

    # No need to `if rc:` because we already tested the run_process result above
    status.commits[step_names.EC_IMAGE] = get_git_commit_data(
        '/mnt/host/source/src/platform/ec/board')

    # create_initial_ec_image.sh will build the ec.bin for this variant
    # if successful.
    ec_dir = '/mnt/host/source/src/platform/ec'
    ec_bin = os.path.join(ec_dir, 'build', status.variant, 'ec.bin')
    logging.debug('ec.bin = "%s"', ec_bin)

    if not os.path.isfile(ec_bin):
        logging.error('EC binary %s not found', ec_bin)
        return False
    return True


def ec_buildall(status):
    """Deprecated function that used to do a make buildall -j for the EC

    The EC repo upload hook used to require a make buildall -j before
    uploading. As of crrev.com/c/2436379 this requirement has been removed,
    so this step is no longer necessary.

    This function still exists so that if someone has a new variant already
    in progress and they update new_variant.py, it won't break. Eventually,
    this function will be removed completely.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True
    """
    logging.info('Running deprecated step ec_buildall')
    del status  # unused parameter
    return True


def add_variant_to_public_yaml(status):
    """Add the new variant to the public model.yaml file

    This function calls add_variant_to_yaml.sh to add the new variant to
    the public model.yaml file.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the script succeeded, False is something failed
    """
    logging.info('Running step add_variant_to_public_yaml')
    add_variant_to_yaml_sh = os.path.join(status.my_loc,
        'add_variant_to_yaml.sh')
    rc = run_process(
        [add_variant_to_yaml_sh,
        status.base,
        status.variant,
        status.bug])
    if rc:
        status.commits[step_names.ADD_PUB_YAML] = get_git_commit_data(
            '/mnt/host/source/src/overlays')
    return rc


def add_variant_to_private_yaml(status):
    """Add the new variant to the private model.yaml file

    This function calls add_variant.sh to add the new variant to
    the private model.yaml file.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the script succeeded, False is something failed
    """
    logging.info('Running step add_variant_to_private_yaml')
    add_variant_sh = os.path.expanduser(os.path.join(status.private_yaml_dir,
                                                     'add_variant.sh'))
    rc = run_process(
        [add_variant_sh,
        status.variant,
        status.bug])
    if rc:
        status.commits[step_names.ADD_PRIV_YAML] = get_git_commit_data(
            status.private_yaml_dir)
    return rc



def build_config(status):
    """Build project config files, from yaml or starlark

    This function builds the project config files that mosys and other tools
    use, then verifies that the new variant's name shows up in all of the
    output files. Depending on the baseboard, the input may be the model.yaml
    files, or the starlark configuration files.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the scripts and build succeeded, False is something failed
    """
    logging.info('Running step build_config')
    if not emerge_with_workon(status, status.config_workon_pkgs,
                              status.emerge_cmd, status.config_emerge_pkgs):
        return False

    # Check the generated config.yaml file for occurences of the variant
    # name to determine if the emerge was successful.
    config_yaml = os.path.join(
        '/build', status.base, 'usr/share/chromeos-config/yaml/config.yaml')
    logging.debug('config_yaml = "%s"', config_yaml)
    if not os.path.isfile(config_yaml):
        logging.error('%s does not exist', config_yaml)
        return False

    if not status.variant in osutils.ReadFile(config_yaml):
        logging.error('variant name %s not found in yaml file %s',
                      status.variant, config_yaml)
        return False

    return True


def emerge_all(status):
    """Build the coreboot BIOS and EC code for the new variant

    This build step will cros_workon start a list of packages provided by
    the reference board data as status.workon_pkgs, then emerge a list of
    packages (status.emerge_pkgs), and then cros_workon stop any packages
    that it started. Any packages that were already being worked on will
    not be stopped.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the build succeeded, False if something failed
    """
    logging.info('Running step emerge_all')
    environ = {**os.environ, 'FW_NAME': status.variant}
    if not emerge_with_workon(status, status.workon_pkgs,
                              status.emerge_cmd, status.emerge_pkgs,
                              env=environ):
        return False

    # Check if the expected build outputs exist.
    build_path = '/build/' + status.base + '/firmware'
    logging.debug('build_path = "%s"', build_path)
    image_bin = 'image-' + status.variant + '.bin'
    if not os.path.isfile(os.path.join(build_path, image_bin)):
        logging.error('emerge failed because %s does not exist', image_bin)
        return False

    serial_bin = 'image-' + status.variant + '.serial.bin'
    if not os.path.isfile(os.path.join(build_path, serial_bin)):
        logging.error('emerge failed because %s does not exist', serial_bin)
        return False

    return True


def push_coreboot(status):
    """Push the coreboot CL to coreboot.org

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the build succeeded, False if something failed
    """
    logging.info('Running step push_coreboot')

    # Set up a return code that may change to False if we find that a
    # coreboot CL has not been uploaded.
    rc = True

    for commit_key in status.coreboot_push_list:
        logging.debug('Processing key %s', commit_key)
        commit = status.commits[commit_key]
        if 'gerrit' not in commit or 'cl_number' not in commit:
            change_id = commit['change_id']
            cl = find_change_id(change_id)
            if cl is not None:
                save_cl_data(status, commit_key, cl)
            else:
                logging.debug('Not found %s, need to upload', change_id)
                logging.error(
                    'The following commit needs to be pushed to coreboot.org:')
                logging.error('  Branch "%s"', commit['branch_name'])
                logging.error('  in directory "%s"', commit['dir'])
                logging.error('  with change-id "%s"', commit['change_id'])
                logging.error('Please push the branch to review.coreboot.org, '
                              'and then re-start this program with --continue')
                # Since this commit needs to be uploaded, do not continue after
                # this step returns.
                rc = False
        else:
            instance_name = commit['gerrit']
            cl_number = commit['cl_number']
            logging.debug('Already uploaded (%s, %s)', instance_name, cl_number)

    return rc


def query_gerrit(instance, change_id):
    """Search a gerrit instance for a specific change_id

    Args:
        instance: gerrit instance to query. Suitable values come from
            gerrit.GetCrosInternal() and gerrit.GetCrosExternal()
        change_id: The change_id to search for

    Returns:
        CL number if found, None if not
    """
    raw = instance.Query(change=change_id, raw=True)
    if raw:
        # If the CL was found by change_id, there will be only one,
        # because the change_id is used to recognize a new patchset
        # on an existing CL.
        return raw[0]['number']

    return None


def query_coreboot_gerrit(change_id):
    """Search the coreboot gerrit for a specific change_id

    Use the REST API to look for the change_id. See
    https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html
    for details on the REST API to search for a change-id.

    We can't use query_gerrit with a manually constructed GerritHelper
    because we need the user's private SSH key to access review.coreboot.org,
    but these are not available inside the chroot.

    Args:
        change_id: The change_id to search for

    Returns:
        CL number if found, None if not
    """
    r = requests.get('https://review.coreboot.org/changes/' + change_id)
    response = r.content.decode('utf-8')
    # Check if the response starts with 'Not found', in which case return None
    if response.startswith('Not found:'):
        return None
    # Strip off the initial )]}'\n that is used as XSS protections, see
    # https://gerrit-review.googlesource.com/Documentation/rest-api.html#output
    # and decode as JSON.
    data = json.loads(response[5:])
    if '_number' in data:
        return str(data['_number'])
    return None


def find_change_id(change_id):
    """Search the public and private ChromeOS gerrit instances for a change-id

    Args:
        change_id: Change-Id to search for in both gerrit instances

    Returns:
        Tuple of the gerrit instance ('chromium' or 'chrome-internal') and
        the CL number if the Change-Id is found.
        None if not found.
    """
    cl_number = query_gerrit(gerrit.GetCrosExternal(), change_id)
    if cl_number:
        return 'chromium', cl_number
    cl_number = query_gerrit(gerrit.GetCrosInternal(), change_id)
    if cl_number:
        return 'chrome-internal', cl_number
    cl_number = query_coreboot_gerrit(change_id)
    if cl_number:
        return 'coreboot', cl_number
    return None


def save_cl_data(status, commit_key, cl):
    """Save the gerrit instance and CL number to the yaml file

    Args:
        status: variant_status object tracking our board, variant, etc.
        commit_key: Which key in the commits map we're processing
        cl: Value returned by find_change_id, should be a tuple
            of instance_name, cl_number
    """
    instance_name, cl_number = cl
    print(f'Found ({instance_name}, {cl_number}), saving to yaml')
    status.commits[commit_key]['gerrit'] = instance_name
    status.commits[commit_key]['cl_number'] = cl_number
    status.save()


def repo_upload(branch_name, cwd):
    """Upload a branch to gerrit

    This function runs `repo upload` in the specified directory to upload
    a branch to gerrit. Because it's operating in a directory and with a
    branch name, it could upload more than one commit, which is OK because
    we'll look for each commit by change-id before trying to upload in that
    directory. For example, this happens in Zork, where the cb_config step
    and the cras_config step both have a commit in src/overlays. When we're
    processing the cb_config step and we `repo upload` in src/overlays, it
    will also upload the commit for cras_config. Then we come around to the
    cras_config step, and since we can find a CL with the change-id, we don't
    try to upload again.

    Args:
        branch_name: the name of the branch to upload. Gets passed to
            repo upload with the --br flag
        cwd: directory where we want to upload. Gets set as the working
            directory for executing repo upload.

    Returns:
        True if repo upload exits with a successful error code, false otherwise
    """
    return run_process(
        ['repo',
        'upload',
        '.',
        '--br=' + branch_name,
        '--wip',
        '--verify',
        '--yes',
        '--hashtag=new_variant'],
        cwd=cwd)


def upload_CLs(status):
    """Upload all CLs to chromiumos

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the build succeeded, False if something failed
    """
    logging.info('Running step upload_CLs')

    for commit_key in status.repo_upload_list:
        logging.debug('Processing key %s', commit_key)
        commit = status.commits[commit_key]
        if 'gerrit' not in commit or 'cl_number' not in commit:
            change_id = commit['change_id']
            cl = find_change_id(change_id)
            if cl is not None:
                save_cl_data(status, commit_key, cl)
            else:
                logging.debug('Not found %s, need to upload', change_id)
                if not repo_upload(commit['branch_name'], commit['dir']):
                    logging.error('Repo upload %s in %s failed!',
                                  commit['branch_name'],
                                  commit['dir'])
                    return False
                cl = find_change_id(change_id)
                if cl is None:
                    logging.error(
                        'repo upload %s succeeded, but change_id is not found!',
                        commit_key)
                    return False
                save_cl_data(status, commit_key, cl)
        else:
            instance_name = commit['gerrit']
            cl_number = commit['cl_number']
            logging.debug('Already uploaded (%s, %s)', instance_name, cl_number)

    return True


def find_coreboot_upstream(status):
    """Find the upstream coreboot CL in chromiumos

    When the coreboot variant CL is first uploaded to review.coreboot.org,
    it is not visible in the chromiumos tree (and also cannot be used as
    a target for cq-depend). There is a process for upstream CLs from
    coreboot after they have been reviewed, approved, and merged. We can
    track a specific coreboot CL if we know the change-id that it used on
    the coreboot gerrit instance, by looking for that change-id in the public
    chromium gerrit instance.

    The change-id for the coreboot variant will be under the 'cb_variant' key,
    but this is for the 'coreboot' gerrit instance.

    When we find the upstreamed CL, we will record the gerrit instance and
    CL number in the yaml file under the 'find' key ("find upstream coreboot")
    so that we don't need to search coreboot again.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the build succeeded, False if something failed
    """
    logging.info('Running step find_coreboot_upstream')

    # If we have already found the upstream coreboot CL, then exit with success
    if step_names.FIND in status.commits:
        commit = status.commits[step_names.FIND]
        if 'gerrit' in commit and 'cl_number' in commit:
            instance_name = commit['gerrit']
            cl_number = commit['cl_number']
            logging.debug('Already found (%s, %s)', instance_name, cl_number)
            return True

    # Make sure we have a CB_VARIANT commit and a change_id for it
    if step_names.CB_VARIANT not in status.commits:
        logging.error('Key %s not found in status.commits',
            step_names.CB_VARIANT)
        return False
    if 'change_id' not in status.commits[step_names.CB_VARIANT]:
        logging.error('Key change_id not found in status.commits[%s]',
            step_names.CB_VARIANT)
        return False

    # Find the CL by the Change-Id
    change_id = status.commits[step_names.CB_VARIANT]['change_id']
    gerrit_query_args = {
        'message': f'Change-Id:{change_id}'
    }
    cros = gerrit.GetCrosExternal()
    upstream = cros.Query(**gerrit_query_args)
    # If nothing is found, the patch hasn't been upstreamed yet
    if not upstream:
        logging.error('Program cannot continue without upstream coreboot CL.')
        logging.error('(coreboot:%s, change-id %s)',
            status.commits[step_names.CB_VARIANT]['cl_number'],
            status.commits[step_names.CB_VARIANT]['change_id'])
        logging.error('Please wait for the upstream CL, then run this program'
                      ' again with --continue')
        return False

    # If more than one CL is found, something is very wrong
    if len(upstream) != 1:
        logging.error('More than one CL was found with Change-Id %s', change_id)
        return False

    # At this point, we know there is only one CL and we can get the
    # repo and CL number by splitting on the colon between them.
    patchlink = upstream[0].PatchLink()
    instance_name, cl_number = patchlink.split(':')

    # Can't use get_git_commit_data because we're not pulling this
    # information from a git commit, but rather from gerrit.
    # We only need the gerrit instance and the CL number so we can have
    # other CLs cq-depend on this CL. The other keys are not needed because:
    # dir - not needed because we're not going to `cd` there to `repo upload`
    # branch_name - not valid; the CL is already merged
    # change_id - we use the change_id to find a CL number, and since we
    #   just found the CL number via change-id, this is moot.
    status.commits[step_names.FIND] = {
        'gerrit': instance_name,
        'cl_number': str(cl_number)
    }

    return True


def calc_cq_depend(status):
    """Determine the list of CLs for each commit that has dependencies.

    status.depends is a map of dependencies from step name to a list of
    steps that the step depends on. For each step, find the SHA of the
    commit, then find the gerrit instance and CL number of the commits
    that it depends on. Construct the Cq-Depends list and save it under
    the 'cq_depend' key, i.e. commit['add_priv_yaml']['cq_depend'] or
    as it will be stored in the yaml:
        commits:
          add_priv_yaml:
            cq_depend: 'chromium:1629121, chromium:1638243'

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if all dependencies have been calculated. False if something
        failed, usually a commit not found by Change-Id.
    """
    logging.info('Running step calc_cq_depend')
    # Iterate through the commits that have dependencies.
    for key in status.depends:
        logging.debug('Processing %s to add dependencies', key)
        # For every commit that has dependencies, find the gerrit instance
        # and CL number of the dependencies.
        cq_depend_list = []
        for depend_key in status.depends[key]:
            depend_commit = status.commits[depend_key]
            if not 'gerrit' in depend_commit:
                logging.error('Commit %s does not have a gerrit instance',
                              depend_key)
                return False
            if not 'cl_number' in depend_commit:
                logging.error('Commit %s does not have a CL number',
                              depend_key)
                return False

            instance_name = depend_commit['gerrit']
            cl_number = depend_commit['cl_number']
            cq_depend_list.append(f'{instance_name}:{cl_number}')

        # Add the 'cq_depend' key to the commit.
        cq_depend_str = 'Cq-Depend: %s' % ', '.join(cq_depend_list)
        logging.debug('Add to commit %s %s', key, cq_depend_str)
        status.commits[key]['cq_depend'] = cq_depend_str

    return True


def add_cq_depend_to_commit_msg(git_repo, change_id, cq_depend_str):
    """Update the commit message with a Cq-Depends line.

    Find the SHA of the commit, then use git filter-branch --msg-filter
    to add the Cq-Depend line just before the Change-Id line. See
    https://chromium.googlesource.com/chromiumos/docs/+/HEAD/contributing.md#cq-depend
    for details about Cq-Depend format and location.

    Args:
        git_repo: Directory of git repository.
        change_id: The Change-Id to search for.
        cq_depend_str: The Cq-Depend string. It must be in the correct format
            per chromeos documentation, ready to insert into the commit msg
            on the line before Change-Id.

    Returns:
        True if `git filter-branch` was successful. False if the command
        failed.
    """
    logging.debug('find SHA of Change-Id %s in %s', change_id, git_repo)
    sha = change_id_to_sha(git_repo, change_id)
    if sha is None:
        logging.error('Cannot find the SHA for Change-Id %s in %s',
                      change_id, git_repo)
        return False
    logging.debug('SHA = %s', sha)

    # Check if the commit message already has a Cq-Depend line.
    msg = get_commit_msg(git_repo, sha)
    if any('Cq-Depend' in tmpstr for tmpstr in msg):
        logging.debug('Already has Cq-Depend')
        return True

    # Use git filter-branch --msg-filter to add the Cq-Depend line just
    # before the Change-Id line.
    environ = {**os.environ, 'FILTER_BRANCH_SQUELCH_WARNING': '1'}
    cmd = [
        'git',
        'filter-branch',
        '-f',
        '--msg-filter',
        f'sed -E "s/^(Change-Id: {change_id})$/{cq_depend_str}\\n\\1/"',
        '--',
        f'{sha}^..']
    return run_process(cmd, cwd=git_repo, env=environ)


def add_cq_depend(status):
    """Add Cq-Depend to commits and flag them for re-upload.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the commit messages have been successfully amended, False if
        something failed.
    """
    logging.info('Running step add_cq_depend')
    for key in status.commits:
        commit = status.commits[key]
        if 'cq_depend' in commit:
            logging.debug('%s has %s', key, commit['cq_depend'])
            # Make sure the commit has a working directory and a change_id
            # before trying to amend its commit message.
            if 'dir' not in commit or 'change_id' not in commit:
                logging.error('Missing dir and/or change_id from %s', key)
                return False

            if not add_cq_depend_to_commit_msg(commit['dir'],
                                               commit['change_id'],
                                               commit['cq_depend']):
                return False
            commit['needs_re_upload'] = True
        else:
            logging.debug('%s no dependencies', key)

    return True


def re_upload(status):
    """Re-upload commits that have changed.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True if the uploads succeeded. False if a repo upload failed.
    """
    logging.info('Running step re_upload')
    for key in status.commits:
        commit = status.commits[key]
        if commit.get('needs_re_upload'):
            logging.debug('Re-upload branch %s in %s', commit['branch_name'],
                          commit['dir'])
            if not repo_upload(commit['branch_name'], commit['dir']):
                logging.error('Repo upload %s in %s failed!',
                              commit['branch_name'],
                              commit['dir'])
                return False
            commit['needs_re_upload'] = False

    return True


def clean_up(status):
    """Final clean-up, including delete the status file

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True
    """
    logging.info('Running step clean_up')
    status.rm()
    return True


def abort(status):
    """Abort the creation of a new variant by abandoning commits

    When the user specifies the --abort flag, we override status.step to
    be 'abort' and there is no transition from 'abort' to anything else.
    We look at status.commits and for each key, see if we have already
    been in that directory and abandoned that specific branch. If not,
    abandon the commit and then add the branch+dir to a list of abandoned
    commits. We do this because some boards (such as Zork) can have multiple
    commits in the same directory and with the same branch name, and we only
    want to repo abandon that branch once.

    Args:
        status: variant_status object tracking our board, variant, etc.

    Returns:
        True
    """
    logging.info('Running step abort')
    # Use the set 'abandoned' to keep track of each branch+dir abandoned.
    abandoned = set()
    for step in status.commits:
        logging.debug('Processing step %s', step)
        commit = status.commits[step]
        branch = commit['branch_name']
        cwd = commit['dir']
        if (branch, cwd) in abandoned:
            logging.debug('Branch %s in directory %s already abandoned',
                          branch, cwd)
        else:
            logging.info('Abandoning branch %s in directory %s',
                         branch, cwd)
            if run_process(['repo', 'abandon', branch, '.'], cwd=cwd):
                abandoned.add((branch, cwd))
            else:
                logging.error('Error while abandoning branch %s', branch)
                return False

    return True


if __name__ == '__main__':
    sys.exit(not int(main()))
