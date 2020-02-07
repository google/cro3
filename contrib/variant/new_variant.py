#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a new variant of an existing reference board

This program will call all of the scripts that create the various pieces
of a new variant. For example to create a new variant of the hatch base
board, the following scripts are called:

* third_party/coreboot/util/mainboard/google/create_coreboot_variant.sh
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

The program has support for multiple reference boards, so the repos, directories,
and scripts above can change depending on what the reference board is.

Copyright 2020 The Chromium OS Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
"""

from __future__ import print_function
import argparse
import importlib
import logging
import os
import re
import shutil
import subprocess
import sys
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
    board, variant, bug, continue_flag = get_args()

    if not check_flags(board, variant, bug, continue_flag):
        return False

    status = get_status(board, variant, bug, continue_flag)
    if status is None:
        return False

    status.load()

    while status.step is not None:
        status.save()
        if not perform_step(status):
            logging.debug('perform_step returned False; exiting ...')
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
        board             Name of the reference board
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
    * coreboot_dir - base directory for coreboot, usually third_party/coreboot
        but could differ for processors that use a private repo
    * cb_config_dir - base directory for coreboot configs, usually
        third_party/chromiumos-overlay/sys-boot/coreboot/files/configs but
        could differ for processors that use a private repo
    * step_list - list of steps (named in step_names.py) to run in sequence
        to create the new variant of the reference board
    * fsp - package name for FSP. This may be None, depending on the
        processor on the reference board
    * fitimage_pkg - package name for the fitimage
    * fitimage_dir - directory for fitimage; prepend '~/trunk/src/' in chroot,
        prepend '~/chromiumos/src' outside the chroot
    * workon_pkgs - list of packages to cros_workon
    * emerge_cmd - the emerge command, e.g. 'emerge-hatch'
    * emerge_pkgs - list of packages to emerge
    * yaml_emerge_pkgs - list of packages to emerge just to build the yaml
    * private_yaml_dir - directory for the private yaml file

    Additionally, the following fields will be set:

    * board - the name of the reference board, e.g. 'hatch'
    * variant - the name of the variant, e.g. 'sushi'
    * bug - optional text for a bug ID, used in the git commit messages.
        Could be 'None' (as text, not the python None), or something like
        'b:12345' for buganizer, or 'chromium:12345'
    * step - internal state tracking, what step of the variant creation
        we are at.
    * yaml_file - internal, just the name of the file where all this data
        gets saved.

    These data might come from the status file (because we read it), or
    they might be the initial values after we created the file (because
    it did not already exist).

    Params:
        board             Name of the reference board
        variant           Name of the variant being created
        bug               Text for bug number, if any ('None' otherwise)
        continue_flag     Flag if --continue was specified

    Returns:
        variant_status object with all the data mentioned above
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

        # We're just starting out, so load the appropriate module and copy
        # all the data from it.
        try:
            module = importlib.import_module(board)
        except ImportError:
            print('Unsupported board "' + board + '"')
            sys.exit(1)

        # pylint: disable=bad-whitespace
        # Allow extra spaces around = so that we can line things up nicely
        status.base                 = module.base
        status.coreboot_dir         = module.coreboot_dir
        status.cb_config_dir        = module.cb_config_dir
        status.emerge_cmd           = module.emerge_cmd
        status.emerge_pkgs          = module.emerge_pkgs
        status.fitimage_dir         = module.fitimage_dir
        status.fitimage_pkg         = module.fitimage_pkg
        status.fitimage_cmd         = module.fitimage_cmd
        status.fsp                  = module.fsp
        status.private_yaml_dir     = module.private_yaml_dir
        status.step_list            = module.step_list
        status.workon_pkgs          = module.workon_pkgs
        status.yaml_emerge_pkgs     = module.yaml_emerge_pkgs
        # pylint: enable=bad-whitespace

        # Start at the first entry in the step list
        status.step = status.step_list[0]

        status.save()

    return status


def perform_step(status):
    """Call the appropriate function for the current step

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the step succeeded, False if it failed
    """
    # Function to call based on the step
    dispatch = {
        step_names.CB_VARIANT:      create_coreboot_variant,
        step_names.CB_CONFIG:       create_coreboot_config,
        step_names.CRAS_CONFIG:     copy_cras_config,
        step_names.ADD_FIT:         add_fitimage,
        step_names.GEN_FIT:         gen_fit_image_outside_chroot,
        step_names.COMMIT_FIT:      commit_fitimage,
        step_names.EC_IMAGE:        create_initial_ec_image,
        step_names.EC_BUILDALL:     ec_buildall,
        step_names.ADD_YAML:        add_variant_to_yaml,
        step_names.BUILD_YAML:      build_yaml,
        step_names.EMERGE:          emerge_all,
        step_names.PUSH:            push_coreboot,
        step_names.UPLOAD:          upload_CLs,
        step_names.FIND:            find_coreboot_upstream,
        step_names.CQ_DEPEND:       add_cq_depends,
        step_names.CLEAN_UP:        clean_up,
    }

    if status.step not in dispatch:
        logging.error('Unknown step "%s", aborting...', status.step)
        sys.exit(1)

    return dispatch[status.step](status)


def move_to_next_step(status):
    """Move to the next step in the list

    Params:
        status      variant_status object tracking our board, variant, etc.
    """
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

    Params:
        args            List of the command and its params
        cwd             If not None, cd to this directory before running
        env             Environment to use for execution; if needed, get
                        os.environ.copy() and add variables. If None, just
                        use the current environment
        capture_output  True if we should capture the stdout, false
                        if we just care about success or not.

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
    try:
        if capture_output:
            output = subprocess.check_output(args, cwd=cwd, env=env,
                stderr=subprocess.STDOUT)
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


def cros_workon(status, action):
    """Call cros_workon for all the 9999 ebuilds we'll be touching

    Params:
        status      variant_status object tracking our board, variant, etc.
        action      'start' or 'stop'

    Returns:
        True if the call to cros_workon was successful, False if failed
    """

    # Build up the command from all the packages in the list
    workon_cmd = ['cros_workon', '--board=' + status.base, action] + status.workon_pkgs
    return bool(run_process(workon_cmd))


def create_coreboot_variant(status):
    """Create source files for a new variant of the reference board in coreboot

    This function calls create_coreboot_variant.sh to set up a new variant
    of the reference board.

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if everything succeeded, False if something failed
    """
    logging.info('Running step create_coreboot_variant')
    create_coreboot_variant_sh = os.path.join(
        os.path.expanduser('~/trunk/src/'),
        status.coreboot_dir,
        'util/mainboard/google/create_coreboot_variant.sh')
    return bool(run_process(
        [create_coreboot_variant_sh,
        status.base,
        status.board,
        status.variant,
        status.bug]))


def create_coreboot_config(status):
    """Create a coreboot configuration for a new variant

    This function calls create_coreboot_config.sh, which will make a copy
    of coreboot.${BOARD} into coreboot.${VARIANT}.

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the script and test build succeeded, False if something failed
    """
    logging.info('Running step create_coreboot_config')
    environ = os.environ.copy()
    if status.cb_config_dir is not None:
        environ['CB_CONFIG_DIR'] = status.cb_config_dir
    create_coreboot_config_sh = os.path.expanduser(
        '~/trunk/src/platform/dev/contrib/variant/create_coreboot_config.sh')
    return bool(run_process(
        [create_coreboot_config_sh,
        status.base,
        status.board,
        status.variant,
        status.bug], env=environ))


def copy_cras_config(status):
    """Copy the cras config for a new variant

    This is only necessary for the Zork baseboard right now.
    This function calls copy_cras_config.sh, which will copy the
    cras config in
    overlays/overlay-${BASE}/chromeos-base/chromeos-bsp-${BASE}/files/cras-config/${BASE}
    to .../${VARIANT}

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the script and test build succeeded, False if something failed
    """
    logging.info('Running step copy_cras_config')
    copy_cras_config_sh = os.path.expanduser(
        '~/trunk/src/platform/dev/contrib/variant/copy_cras_config.sh')
    return bool(run_process(
        [copy_cras_config_sh,
        status.base,
        status.board,
        status.variant,
        status.bug]))


def add_fitimage(status):
    """Add the source files for a fitimage for the new variant

    This function calls add_fitimage.sh to create a new XSL file for the
    variant's fitimage, which can override settings from the reference board's
    XSL. When this is done, the user will have to build the fitimage by running
    gen_fit_image.sh outside of the chroot (and outside of this program's
    control) because gen_fit_image.sh uses WINE, which is not installed in
    the chroot. (There is a linux version of FIT, but it requires Open GL,
    which is also not installed in the chroot.)

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the script succeeded, False otherwise
    """
    logging.info('Running step add_fitimage')
    add_fitimage_sh = os.path.expanduser(os.path.join(
        '~/trunk/src', status.fitimage_dir, 'files/add_fitimage.sh'))
    return bool(run_process(
        [add_fitimage_sh,
        status.variant,
        status.bug]))


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
    logging.info('Running step gen_fit_image_outside_chroot')
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
    logging.info(status.fitimage_cmd, status.variant)
    logging.info('Then re-start this program with --continue.')
    logging.info('If your chroot is based in ~/chromiumos, then the folder you want is')
    logging.info('~/chromiumos/src/%s/asset_generation', status.fitimage_dir)
    return False


def check_fit_image_files(status):
    """Check if the fitimage has been generated

    This function is not called directly as a step, and so it doesn't need
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
    outputs_dir = os.path.expanduser(os.path.join(
        '~/trunk/src', status.fitimage_dir, 'asset_generation/outputs'))
    logging.debug('outputs_dir = "%s"', outputs_dir)

    files = []
    if not file_exists(outputs_dir, 'fitimage-' + status.variant + '.bin'):
        files.append('fitimage-' + status.variant + '.bin')

    if not file_exists(outputs_dir,
                       'fitimage-' + status.variant + '-versions.txt'):
        files.append('fitimage-' + status.variant + '-versions.txt')

    if not file_exists(outputs_dir, 'fit.log'):
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
    logging.info('Running step commit_fitimage')
    fitimage_dir = os.path.expanduser(os.path.join('~/trunk/src', status.fitimage_dir))
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

    if not bool(run_process(
        ['git', 'add',
        'asset_generation/outputs/fit.log',
        'files/fitimage-' + status.variant + '.bin',
        'files/fitimage-' + status.variant + '-versions.txt'
        ],
        cwd=fitimage_dir)):
        return False

    return bool(run_process(['git', 'commit', '--amend', '--no-edit'],
        cwd=fitimage_dir))


def create_initial_ec_image(status):
    """Create an EC image for the variant as a clone of the reference board

    This function calls create_initial_ec_image.sh, which will clone the
    reference board to create the variant. The shell script will build the
    EC code for the variant, but the repo upload hook insists that we
    have done a `make buildall` before it will allow an upload, so this
    function does the buildall.

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the script and test build succeeded, False if something failed
    """
    logging.info('Running step create_initial_ec_image')
    create_initial_ec_image_sh = os.path.expanduser(
        '~/trunk/src/platform/dev/contrib/variant/create_initial_ec_image.sh')
    if not bool(run_process(
        [create_initial_ec_image_sh,
        status.board,
        status.variant,
        status.bug])):
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
    logging.info('Running step ec_buildall')
    del status  # unused parameter
    ec = os.path.expanduser('~/trunk/src/platform/ec')
    logging.debug('ec = "%s"', ec)
    return bool(run_process(['make', 'buildall', '-j'], cwd=ec))


def add_variant_to_yaml(status):
    """Add the new variant to the public and private model.yaml files

    This function calls add_variant_to_yaml.sh (the public yaml) and
    add_variant.sh (the private yaml) to add the new variant to
    the yaml files.

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the scripts and build succeeded, False is something failed
    """
    logging.info('Running step add_variant_to_yaml')
    add_variant_to_yaml_sh = os.path.expanduser(
        '~/trunk/src/platform/dev/contrib/variant/add_variant_to_yaml.sh')
    if not bool(run_process(
        [add_variant_to_yaml_sh,
        status.base,
        status.variant,
        status.bug])):
        return False

    add_variant_sh = os.path.expanduser(os.path.join(status.private_yaml_dir, 'add_variant.sh'))
    return bool(run_process(
        [add_variant_sh,
        status.variant,
        status.bug]))


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
    logging.info('Running step build_yaml')
    if not bool(run_process([status.emerge_cmd] + status.yaml_emerge_pkgs)):
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
    # Note that we leave out yaml/model.yaml (the public one) because for
    # some boards, there is nothing in the public yaml file.
    # We gather the output from grep, then look for any of the strings
    # ending in :0. If none of them match, then we're good, but if even
    # one of them ends with :0 then there was a problem with generating
    # the files from the yaml.
    chromeos_config = '/build/' + status.base + '/usr/share/chromeos-config'
    logging.debug('chromeos_config = "%s"', chromeos_config)
    grep = run_process(
        ['grep',
        '-ci',
        status.variant,
        'config.json',
        'yaml/config.c',
        'yaml/config.yaml',
        'yaml/private-model.yaml'], cwd=chromeos_config, capture_output=True)

    if grep is None:
        return False

    return not bool([s for s in grep if re.search(r':0$', s)])


def emerge_all(status):
    """Build the coreboot BIOS and EC code for the new variant

    Params:
        status      variant_status object tracking our board, variant, etc.

    Returns:
        True if the build succeeded, False if something failed
    """
    logging.info('Running step emerge_all')
    cros_workon(status, 'start')
    environ = os.environ.copy()
    environ['FW_NAME'] = status.variant
    # Build up the command for emerge from all the packages in the list
    emerge_cmd_and_params = [status.emerge_cmd] + status.emerge_pkgs
    if not bool(run_process(emerge_cmd_and_params, env=environ)):
        return False

    cros_workon(status, 'stop')
    build_path = '/build/' + status.base + '/firmware'
    logging.debug('build_path = "%s"', build_path)
    if not file_exists(build_path, 'image-' + status.variant + '.bin'):
        logging.error('emerge failed because image-%s.bin does not exist',
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
    logging.info('Running step push_coreboot')
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
    logging.info('Running step upload_CLs')
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
    logging.info('Running step find_coreboot_upstream')
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
    logging.info('Running step add_cq_depends')
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
    logging.info('Running step clean_up')
    status.rm()
    return True


if __name__ == '__main__':
    sys.exit(not int(main()))
