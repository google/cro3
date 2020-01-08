#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a new variant of an existing base board

This program will call all of the scripts that create the various pieces
of a new variant. For example to create a new variant of the hatch base
board, the following scripts are called:

* third_party/coreboot/util/mainboard/google/hatch/create_coreboot_variant.sh
* platform/dev/contrib/variant/create_coreboot_config.sh
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
* platform/ec
* private-overlays/overlay-hatch-private
* overlays

Copyright 2019 The Chromium OS Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
"""

from __future__ import print_function
import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
import variant_status


def main():
    """Create a new variant of an existing base board

    This program automates the creation of a new variant of an existing
    base board by calling various scripts that clone the base board, modify
    files for the new variant, stage commits, and upload to gerrit.

    Note that one of the following is required:
    * --continue
    * --board=BOARD --variant=VARIANT [--bug=BUG]
    """
    board, variant, bug, continue_flag = get_args()

    if not check_flags(board, variant, bug, continue_flag):
        return False

    status = get_status(board, variant, bug, continue_flag)
    if status is None:
        return False

    status.load()

    while status.stage is not None:
        status.save()
        if not perform_stage(status):
            logging.debug('perform_stage returned False; exiting ...')
            return False

        move_to_next_stage(status)

    return True


def get_args():
    """Parse the command-line arguments

    There doesn't appear to be a way to specify that --continue is
    mutually exclusive with --board, --variant, and --bug. As a result,
    all arguments are optional, and another function will apply the logic
    to check if there is an illegal combination of arguments.

    Returns a list of:
        board             Name of the base board
        variant           Name of the variant being created
        bug               Text for bug number, if any ('None' otherwise)
        continue_flag     Flag if --continue was specified
    """
    parser = argparse.ArgumentParser(
        description=main.__doc__,
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--board', type=str, help='Name of the base board')
    parser.add_argument(
        '--variant', type=str, help='Name of the new variant to create')
    parser.add_argument(
        '--bug', type=str, help='Bug number to reference in commits')
    parser.add_argument(
        '--continue', action='store_true',
        dest='continue_flag', help='Continue the process from where it paused')
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

    return (board, variant, bug, args.continue_flag)


def check_flags(board, variant, bug, continue_flag):
    """Check the flags to ensure no invalid combinations

    We allow any of the following:
    --continue
    --board=board_name --variant=variant_name
    --board=board_name --variant=variant_name --bug=bug_text

    The argument parser does have the functionality to represent the
    combination of --board and --variant as a single mutually-exclusive
    argument, so we have to use this function to do the checking.

    Params:
        board             Name of the base board
        variant           Name of the variant being created
        bug               Text for bug number, if any ('None' otherwise)
        continue_flag     Flag if --continue was specified

    Returns:
        True if the arguments are acceptable, False otherwise
    """
    if continue_flag:
        if board is not None or variant is not None:
            logging.error('--continue cannot have other options')
            return False

        if bug != 'None':
            logging.error('--continue cannot have other options')
            return False
    else:
        if board is None:
            logging.error('--board must be specified')
            return False

        if variant is None:
            logging.error('--variant must be specified')
            return False

    return True


def file_exists(filepath, filename):
    """Determine if a path and file exists

    Params:
        filepath      Path where build outputs should be found, e.g.
                      /build/hatch/firmware
        filename      File that should exist in that path, e.g.
                      image-sushi.bin

    Returns:
        True if file exists in that path, False otherwise
    """
    fullname = os.path.join(filepath, filename)
    return os.path.exists(fullname) and os.path.isfile(fullname)


def get_status(board, variant, bug, continue_flag):
    """Create the status file or get the previous status

    This program can stop at several places as we have to wait for CLs
    to work through CQ or be upstreamed into the chromiumos tree, so just
    like a git cherry-pick, there is a --continue option to pick up where
    you left off.

    If the --continue flag is present, make sure that the status file
    exists, and fail if it doesn't.

    If the --continue flag is not present, then create the status file
    with the board, variant, and bug details. If the status file already
    exists, this is an error case.

    The function returns an object with several fields:
    * board - the name of the baseboard, e.g. 'hatch'
    * variant - the name of the variant, e.g. 'sushi'
    * bug - optional text for a bug ID, used in the git commit messages.
        Could be 'None' (as text, not the python None), or something like
        'b:12345' for buganizer, or 'chromium:12345'
    * workon - list of packages that will need `cros_workon start` before
        we can `emerge`. Each function can add package names to this list.
    * emerge - list of packages that we need to `emerge` at the end. Each
        functions can add package names to this list.
    * stage - internal state tracking, what stage of the variant creation
        we are at.
    * yaml_file - internal, just the name of the file where all this data
        gets saved.

    These data might come from the status file (because we read it), or
    they might be the initial values after we created the file (because
    it did not already exist).

    Params:
        board             Name of the base board
        variant           Name of the variant being created
        bug               Text for bug number, if any ('None' otherwise)
        continue_flag     Flag if --continue was specified

    Returns:
        variant_status object that points to the yaml file
    """
    status = variant_status.variant_status()
    if continue_flag:
        if not status.yaml_file_exists():
            logging.error(
                'new_variant is not in progress; nothing to --continue')
            return None
    else:
        if status.yaml_file_exists():
            logging.error(
                'new_variant already in progress; did you forget --continue?')
            return None

        status.board = board
        status.variant = variant
        status.bug = bug

        if board not in ['hatch', 'volteer']:
            print('Unsupported baseboard "' + board + '"')
            sys.exit(1)

        # Depending on the board, we can have different values here
        if board == 'hatch':
            status.stage = 'cb_variant'
            status.stage_list = [CB_VARIANT, CB_CONFIG, ADD_FIT, GEN_FIT,
                COMMIT_FIT, EC_IMAGE, EC_BUILDALL, ADD_YAML, BUILD_YAML,
                EMERGE, PUSH, UPLOAD, FIND, CQ_DEPEND, CLEAN_UP]

        if board == 'volteer':
            # TODO(pfagerburg) this list of stages will change
            status.stage = 'cb_variant'
            status.stage_list = [CB_VARIANT, CB_CONFIG, ADD_FIT, GEN_FIT,
                COMMIT_FIT, EC_IMAGE, EC_BUILDALL, ADD_YAML, BUILD_YAML,
                EMERGE, PUSH, UPLOAD, FIND, CQ_DEPEND, CLEAN_UP]

        status.save()

    return status


# Constants for the stages, so we don't have to worry about misspelling them
# pylint: disable=bad-whitespace
# Allow extra spaces around = so that we can line things up nicely
CB_VARIANT    = 'cb_variant'
CB_CONFIG     = 'cb_config'
ADD_FIT       = 'add_fit'
GEN_FIT       = 'gen_fit'
COMMIT_FIT    = 'commit_fit'
EC_IMAGE      = 'ec_image'
EC_BUILDALL   = 'ec_buildall'
ADD_YAML      = 'add_yaml'
BUILD_YAML    = 'build_yaml'
EMERGE        = 'emerge'
PUSH          = 'push'
UPLOAD        = 'upload'
FIND          = 'find'
CQ_DEPEND     = 'cq_depend'
CLEAN_UP      = 'clean_up'
# pylint: enable=bad-whitespace


def perform_stage(status):
    """Call the appropriate function for the current stage

    Params:
        st  dictionary that provides details including
            the board name, variant name, and bug ID

    Returns:
        True if the stage succeeded, False if it failed
    """
    # Function to call based on the stage
    dispatch = {
        CB_VARIANT:     create_coreboot_variant,
        CB_CONFIG:      create_coreboot_config,
        ADD_FIT:        add_fitimage,
        GEN_FIT:        gen_fit_image_outside_chroot,
        COMMIT_FIT:     commit_fitimage,
        EC_IMAGE:       create_initial_ec_image,
        EC_BUILDALL:    ec_buildall,
        ADD_YAML:       add_variant_to_yaml,
        BUILD_YAML:     build_yaml,
        EMERGE:         emerge_all,
        PUSH:           push_coreboot,
        UPLOAD:         upload_CLs,
        FIND:           find_coreboot_upstream,
        CQ_DEPEND:      add_cq_depends,
        CLEAN_UP:       clean_up,
    }

    if status.stage not in dispatch:
        logging.error('Unknown stage "%s", aborting...', status.stage)
        sys.exit(1)

    return dispatch[status.stage](status)


def move_to_next_stage(status):
    """Move to the next stage in the list

    Params:
        status      variant_status object tracking our board, variant, etc.
    """
    if status.stage not in status.stage_list:
        logging.error('Unknown stage "%s", aborting...', status.stage)
        sys.exit(1)

    idx = status.stage_list.index(status.stage)
    if idx == len(status.stage_list)-1:
        status.stage = None
    else:
        status.stage = status.stage_list[idx+1]


def run_process(args, *, cwd=None, env=None):
    """Wrapper for subprocess.run that will produce debug-level messages

    Params:
        LImited subset, same as for subprocess.run

    Returns:
        Return value from subprocess.run
    """
    logging.debug('Run %s', str(args))
    retval = subprocess.run(args, cwd=cwd, env=env).returncode
    logging.debug('process returns %s', str(retval))
    return retval


def cros_workon(status, action):
    """Call cros_workon for all the 9999 ebuilds we'll be touching

    TODO(pfagerburg) detect 9999 ebuild to know if we have to workon the package

    Params:
        status      variant_status object tracking our board, variant, etc.
        action      'start' or 'stop'

    Returns:
        True if the call to cros_workon was successful, False if failed
    """

    # Build up the command from all the packages in the list
    workon_cmd = ['cros_workon', '--board=' + status.board, action] + status.workon
    return run_process(workon_cmd) == 0


def create_coreboot_variant(status):
    """Create source files for a new variant of the base board in coreboot

    This function calls create_coreboot_variant.sh to set up a new variant
    of the base board.

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if everything succeeded, False if something failed
    """
    logging.info('Running stage create_coreboot_variant')
    status.workon += ['coreboot', 'libpayload', 'vboot_reference',
        'depthcharge']
    # Despite doing the workon here, we don't add this to emerge, because
    # without the configuration (create_coreboot_config), `emerge coreboot`
    # won't build the new variant.
    status.emerge += ['libpayload', 'vboot_reference', 'depthcharge',
        'chromeos-bootimage']

    create_coreboot_variant_sh = os.path.join(
        os.path.expanduser('~/trunk/src/third_party/coreboot'),
        'util/mainboard/google/create_coreboot_variant.sh')
    return run_process(
        [create_coreboot_variant_sh,
        status.board,
        status.variant,
        status.bug]) == 0


def create_coreboot_config(status):
    """Create a coreboot configuration for a new variant

    This function calls create_coreboot_config.sh, which will make a copy
    of coreboot.${BOARD} into coreboot.${VARIANT}.

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the script and test build succeeded, False if something failed
    """
    logging.info('Running stage create_coreboot_config')
    status.emerge += ['coreboot']
    create_coreboot_config_sh = os.path.expanduser(
        '~/trunk/src/platform/dev/contrib/variant/create_coreboot_config.sh')
    return run_process(
        [create_coreboot_config_sh,
        status.board,
        status.variant,
        status.bug]) == 0


def add_fitimage(status):
    """Add the source files for a fitimage for the new variant

    This function calls add_fitimage.sh to create a new XSL file for the
    variant's fitimage, which can override settings from the base board's XSL.
    When this is done, the user will have to build the fitimage by running
    gen_fit_image.sh outside of the chroot (and outside of this program's
    control) because gen_fit_image.sh uses WINE, which is not installed in
    the chroot. (There is a linux version of FIT, but it requires Open GL,
    which is also not installed in the chroot.)

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the script succeeded, False otherwise
    """
    logging.info('Running stage add_fitimage')
    pkg = 'coreboot-private-files-' + status.board
    # The FSP depends on the baseboard model. We don't have to check for
    # the baseboard not being in this hash because we already checked
    # for an unsupported baseboard when the script started.
    fsp = {
        'hatch': 'intel-cmlfsp',
        'volteer': 'intel-tglfsp'
    }
    status.workon += [fsp[status.board], pkg]
    status.emerge += [fsp[status.board], pkg]
    add_fitimage_sh = os.path.expanduser(os.path.join(
        '~/trunk/src/private-overlays',
        'baseboard-' + status.board + '-private',
        'sys-boot',
        'coreboot-private-files-' + status.board,
        'files/add_fitimage.sh'))
    return run_process(
        [add_fitimage_sh,
        status.variant,
        status.bug]) == 0


def gen_fit_image_outside_chroot(status):
    """Tell the user to run gen_fit_image.sh outside the chroot

    As noted for add_Fitimage(), gen_fit_image.sh cannot run inside the
    chroot. This function tells the user to run gen_fit_image.sh in
    their normal environment, and then come back (--continue) when that
    is done.

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True
    """
    logging.info('Running stage gen_fit_image_outside_chroot')
    fit_image_files = check_fit_image_files(status)
    # If the list is empty, then `not` of the list is True, so the files
    # we need are all present and we can continue.
    if not fit_image_files:
        return True

    logging.info('The following files need to be generated:')
    for filename in fit_image_files:
        logging.info('* %s', filename)
    logging.info('The fitimage sources are ready for gen_fit_image.sh to process.')
    logging.info('gen_fit_image.sh cannot run inside the chroot. Please open a new terminal')
    logging.info('window, change to the directory where gen_fit_image.sh is located, and run')
    logging.info('./gen_fit_image.sh %s [location of FIT] -b', status.variant)
    logging.info('Then re-start this program with --continue.')
    logging.info('If your chroot is based in ~/chromiumos, then the folder you want is')
    logging.info('~/chromiumos/src/private-overlays/baseboard-%s-private/sys-boot'
        '/coreboot-private-files-%s/asset_generation', status.board, status.board)
    return False


def check_fit_image_files(status):
    """Check if the fitimage has been generated

    This function is not called directly as a stage, and so it doesn't need
    to produce any error messages to the user (except with --verbose).
    gen_fit_image_outside_chroot will call this function to see if the
    fitimage files exist, and if not, then that function will print the
    message about how the user needs to run gen_fit_image.sh outside the
    chroot.

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        List of files that *DO NOT* exist and need to be created, [] if
        all files are present.
    """
    fitimage_dir = os.path.expanduser(os.path.join(
        '~/trunk/src/private-overlays',
        'baseboard-' + status.board + '-private',
        'sys-boot',
        'coreboot-private-files-' + status.board,
        'asset_generation/outputs'))
    logging.debug('fitimage_dir = "%s"', fitimage_dir)

    files = []
    if not file_exists(fitimage_dir, 'fitimage-' + status.variant + '.bin'):
        files.append('fitimage-' + status.variant + '.bin')

    if not file_exists(fitimage_dir,
                       'fitimage-' + status.variant + '-versions.txt'):
        files.append('fitimage-' + status.variant + '-versions.txt')

    if not file_exists(fitimage_dir, 'fit.log'):
        files.append('fit.log')

    return files


def move_fitimage_file(fitimage_dir, filename):
    """Move fitimage files from create-place to commit-place

    commit_fitimage needs to move the fitimage files from the place where
    they were created to a different directory in the tree. This utility
    function handles joining paths and calling a file move function.

    Params:
        fitimage_dir    Directory where the fitimage files are
        filename        Name of the file being moved

    Returns:
        True if the move succeeded, False if it failed
    """
    src_dir = os.path.join(fitimage_dir, 'asset_generation/outputs')
    src = os.path.join(src_dir, filename)
    dest_dir = os.path.join(fitimage_dir, 'files')
    dest = os.path.join(dest_dir, filename)
    # If src does not exist and dest does, the move is already done => success!
    if not file_exists(src_dir, filename) and file_exists(dest_dir, filename):
        logging.debug('move "%s", "%s" unnecessary because dest exists and'
            ' src does not exist', src, dest)
        return True

    logging.debug('move "%s", "%s"', src, dest)
    return shutil.move(src, dest)


def commit_fitimage(status):
    """Move the fitimage files and add them to a git commit

    This function moves the fitimage binary and -versions files from
    asset_generation/outputs to files/ and then adds those files and
    fit.log to the existing git commit.

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the copy, git add, and git commit --amend all succeeded.
        False if something failed.
    """
    logging.info('Running stage commit_fitimage')
    fitimage_dir = os.path.expanduser(os.path.join(
        '~/trunk/src/private-overlays',
        'baseboard-' + status.board + '-private',
        'sys-boot',
        'coreboot-private-files-' + status.board))
    logging.debug('fitimage_dir  = "%s"', fitimage_dir)

    # The copy operation will check that the source file exists, so no
    # need to check separately.
    if not move_fitimage_file(fitimage_dir,
                              'fitimage-' + status.variant + '.bin'):
        logging.error('Moving fitimage binary failed')
        return False

    if not move_fitimage_file(fitimage_dir,
                              'fitimage-' + status.variant + '-versions.txt'):
        logging.error('Moving fitimage versions.txt failed')
        return False

    if run_process(
        ['git', 'add',
        'asset_generation/outputs/fit.log',
        'files/fitimage-' + status.variant + '.bin',
        'files/fitimage-' + status.variant + '-versions.txt'
        ],
        cwd=fitimage_dir) != 0:
        return False

    return run_process(['git', 'commit', '--amend', '--no-edit'],
        cwd=fitimage_dir) == 0


def create_initial_ec_image(status):
    """Create an EC image for the variant as a clone of the base board

    This function calls create_initial_ec_image.sh, which will clone the
    base board to create the variant. The shell script will build the
    EC code for the variant, but the repo upload hook insists that we
    have done a `make buildall` before it will allow an upload, so this
    function does the buildall.

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the script and test build succeeded, False if something failed
    """
    logging.info('Running stage create_initial_ec_image')
    status.workon += ['chromeos-ec']
    status.emerge += ['chromeos-ec']
    create_initial_ec_image_sh = os.path.expanduser(
        '~/trunk/src/platform/dev/contrib/variant/create_initial_ec_image.sh')
    if run_process(
        [create_initial_ec_image_sh,
        status.board,
        status.variant,
        status.bug]) != 0:
        return False

    # create_initial_ec_image.sh will build the ec.bin for this variant
    # if successful.
    ec = os.path.expanduser('~/trunk/src/platform/ec')
    logging.debug('ec = "%s"', ec)
    ec_bin = 'build/' + status.variant + '/ec.bin'
    logging.debug('ec.bin = "%s"', ec_bin)

    return file_exists(ec, ec_bin)


def ec_buildall(status):
    """Do a make buildall -j for the EC, which is required for repo upload

    The upload hook checks to ensure that the entire EC codebase builds
    without error, so we have to run make buildall -j before uploading.

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the script and test build succeeded, False if something failed
    """
    logging.info('Running stage ec_buildall')
    del status  # unused parameter
    ec = os.path.expanduser('~/trunk/src/platform/ec')
    logging.debug('ec = "%s"', ec)
    return run_process(['make', 'buildall', '-j'], cwd=ec) == 0


def add_variant_to_yaml(status):
    """Add the new variant to the public and private model.yaml files

    This function calls add_variant_to_yaml.sh (the public yaml) and
    add_variant.sh (the private yaml) to add the new variant to
    the yaml files.

    Params:
        st  dictionary that provides details including
            the board name, variant name, and bug ID

    Returns:
        True if the scripts and build succeeded, False is something failed
    """
    logging.info('Running stage add_variant_to_yaml')
    # TODO(pfagerburg) these can change in response to firmware changes
    # or new board-specific support scripts that might handle the entire
    # build or at least specify the packages so that this program doesn't
    # have to know.
    status.workon += ['chromeos-config-bsp-' + status.board + '-private']
    status.emerge += ['chromeos-config', 'chromeos-config-bsp',
        'chromeos-config-bsp-' + status.board,
        'chromeos-config-bsp-' + status.board + '-private',
        'coreboot-private-files', 'coreboot-private-files-' + status.board]
    add_variant_to_yaml_sh = os.path.expanduser(
        '~/trunk/src/platform/dev/contrib/variant/add_variant_to_yaml.sh')
    if run_process(
        [add_variant_to_yaml_sh,
        status.board,
        status.variant,
        status.bug
        ]) != 0:
        return False

    add_variant_sh = os.path.expanduser(os.path.join(
        '~/trunk/src/private-overlays',
        'overlay-' + status.board + '-private',
        'chromeos-base',
        'chromeos-config-bsp-' + status.board + '-private',
        'add_variant.sh'))
    if run_process(
        [add_variant_sh,
        status.variant,
        status.bug
        ]) != 0:
        return False

    return True


def build_yaml(status):
    """Build config files from the yaml files

    This function builds the yaml files into the JSON and C code that
    mosys and other tools use, then verifies that the new variant's name
    shows up in all of the output files.

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the scripts and build succeeded, False is something failed
    """
    logging.info('Running stage build_yaml')
    if run_process(
        ['emerge-' + status.board,
        'chromeos-config-bsp-' + status.board,
        'chromeos-config-bsp-' + status.board + '-private',
        'chromeos-config-bsp',
        'chromeos-config']) != 0:
        return False

    # Check generated files for occurences of the variant name.
    # Each file should have at least one occurence, so use `grep -c` to
    # count the occurrences of the variant name in each file.
    # The results will be something like this:
    #   config.json:10
    #   yaml/config.c:6
    #   yaml/config.yaml:27
    #   yaml/model.yaml:6
    #   yaml/private-model.yaml:10
    # If the variant name doesn't show up in the file, then the count
    # will be 0, so we would see, e.g.
    #   config.json:0
    # We gather the output from grep, decode as UTF-8, split along newlines,
    # and then look for any of the strings ending in :0. If none of them
    # match, then we're good, but if even one of them ends with :0 then
    # there was a problem with generating the files from the yaml.
    chromeos_config = '/build/' + status.board + '/usr/share/chromeos-config'
    logging.debug('chromeos_config = "%s"', chromeos_config)
    # Can't use run because we need to capture the output instead
    # of a status code.
    grep = subprocess.check_output(
        ['grep',
        '-c',
        status.variant,
        'config.json',
        'yaml/config.c',
        'yaml/config.yaml',
        'yaml/model.yaml',
        'yaml/private-model.yaml'], cwd=chromeos_config)
    # Convert from byte string to ASCII
    grep = grep.decode('utf-8')
    # Split into array of individual lines
    grep = grep.split('\n')
    return not bool([s for s in grep if re.search(r':0$', s)])


def emerge_all(status):
    """Build the coreboot BIOS and EC code for the new variant

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the build succeeded, False if something failed
    """
    logging.info('Running stage emerge_all')
    cros_workon(status, 'start')
    environ = os.environ.copy()
    environ['FW_NAME'] = status.variant
    # Build up the command for emerge from all the packages in the list
    emerge_cmd_and_params = ['emerge-' + status.board] + status.emerge
    if run_process(emerge_cmd_and_params, env=environ) != 0:
        return False

    cros_workon(status, 'stop')
    build_path = '/build/' + status.board + '/firmware'
    logging.debug('build_path = "%s"', build_path)
    if not file_exists(build_path, 'image-' + status.variant + '.bin'):
        logging.error('emerge failed because image-%s.bin does not exist',
            status.variant)
        return False

    if not file_exists(build_path, 'image-' + status.variant + '.dev.bin'):
        logging.error('emerge failed because image-%s.dev.bin does not exist',
            status.variant)
        return False

    if not file_exists(build_path, 'image-' + status.variant + '.net.bin'):
        logging.error('emerge failed because image-%s.net.bin does not exist',
            status.variant)
        return False

    if not file_exists(build_path, 'image-' + status.variant + '.serial.bin'):
        logging.error('emerge failed because image-%s.serial.bin does not exist',
            status.variant)
        return False

    return True


def push_coreboot(status):
    """Push the coreboot CL to coreboot.org

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the build succeeded, False if something failed
    """
    logging.info('Running stage push_coreboot')
    del status  # unused parameter
    logging.error('TODO (pfagerburg): implement push_coreboot')
    return True


def upload_CLs(status):
    """Upload all CLs to chromiumos

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the build succeeded, False if something failed
    """
    logging.info('Running stage upload_CLs')
    del status  # unused parameter
    logging.error('TODO (pfagerburg): implement upload_CLs')
    return True


def find_coreboot_upstream(status):
    """Find the coreboot CL after it has been upstreamed to chromiumos

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the build succeeded, False if something failed
    """
    logging.info('Running stage find_coreboot_upstream')
    del status  # unused parameter
    logging.error('TODO (pfagerburg): implement find_coreboot_upstream')
    return True


def add_cq_depends(status):
    """Add Cq-Depends to all of the CLs in chromiumos

    The CL in coreboot needs to be pushed to coreboot.org, get merged,
    and then get upstreamed into the chromiumos tree before the other
    CLs can cq-depend on it and pass CQ.

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the build succeeded, False if something failed
    """
    logging.info('Running stage add_cq_depends')
    del status  # unused parameter
    logging.error('TODO (pfagerburg): implement add_cq_depends')
    return True


def clean_up(status):
    """Final clean-up, including delete the status file

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True
    """
    logging.info('Running stage clean_up')
    status.rm()
    return True


if __name__ == '__main__':
    sys.exit(not int(main()))
