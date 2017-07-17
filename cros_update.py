# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An executable function cros-update for auto-update of a CrOS host.

The reason to create this file is to let devserver to trigger a background
process for CrOS auto-update. Therefore, when devserver service is restarted
sometimes, the CrOS auto-update process is still running and the corresponding
provision task won't claim failure.

It includes two classes:
  a. CrOSUpdateTrigger:
    1. Includes all logics which identify which types of update need to be
       performed in the current DUT.
    2. Responsible for write current status of CrOS auto-update process into
       progress_tracker.

  b. CrOSAUParser:
    1. Pre-setup the required args for CrOS auto-update.
    2. Parse the input parameters for cmd that runs 'cros_update.py'.
"""

from __future__ import print_function

import argparse
import cros_update_logging
import cros_update_progress
import logging
import os
import sys
import traceback

# only import setup_chromite before chromite import.
import setup_chromite # pylint: disable=unused-import
try:
  from chromite.lib import auto_updater
  from chromite.lib import remote_access
  from chromite.lib import timeout_util
except ImportError as e:
  logging.debug('chromite cannot be imported: %r', e)
  auto_updater = None
  remote_access = None
  timeout_util = None

# The build channel for recovering host's stateful partition
STABLE_BUILD_CHANNEL = 'stable-channel'

# Timeout for CrOS auto-update process.
CROS_UPDATE_TIMEOUT_MIN = 30

# The preserved path in remote device, won't be deleted after rebooting.
CROS_PRESERVED_PATH = ('/mnt/stateful_partition/unencrypted/'
                       'preserve/cros-update')

# Standard error tmeplate to be written into status tracking log.
CROS_ERROR_TEMPLATE = cros_update_progress.ERROR_TAG + ' %s'


class CrOSAUParser(object):
  """Custom command-line options parser for cros-update."""
  def __init__(self):
    self.args = sys.argv[1:]
    self.parser = argparse.ArgumentParser(
        usage='%(prog)s [options] [control-file]')
    self.SetupOptions()
    self.removed_args = []

    # parse an empty list of arguments in order to set self.options
    # to default values.
    self.options = self.parser.parse_args(args=[])

  def SetupOptions(self):
    """Setup options to call cros-update command."""
    self.parser.add_argument('-d', action='store', type=str,
                             dest='host_name',
                             help='host_name of a DUT')
    self.parser.add_argument('-b', action='store', type=str,
                             dest='build_name',
                             help='build name to be auto-updated')
    self.parser.add_argument('--static_dir', action='store', type=str,
                             dest='static_dir',
                             help='static directory of the devserver')
    self.parser.add_argument('--force_update', action='store_true',
                             dest='force_update', default=False,
                             help=('force an update even if the version '
                                   'installed is the same'))
    self.parser.add_argument('--full_update', action='store_true',
                             dest='full_update', default=False,
                             help=('force a rootfs update, skip stateful '
                                   'update'))
    self.parser.add_argument('--original_build', action='store', type=str,
                             dest='original_build', default='',
                             help=('force stateful update with the same '
                                   'version of previous rootfs partition'))
    self.parser.add_argument('--payload_filename', action='store', type=str,
                             dest='payload_filename', default=None,
                             help='A custom payload filename')
    self.parser.add_argument('--clobber_stateful', action='store_true',
                             dest='clobber_stateful', default=False,
                             help='Whether to clobber stateful')

  def ParseArgs(self):
    """Parse and process command line arguments."""
    # Positional arguments from the end of the command line will be included
    # in the list of unknown_args.
    self.options, unknown_args = self.parser.parse_known_args()
    # Filter out none-positional arguments
    while unknown_args and unknown_args[0][0] == '-':
      self.removed_args.append(unknown_args.pop(0))
      # Always assume the argument has a value.
      if unknown_args:
        self.removed_args.append(unknown_args.pop(0))
    if self.removed_args:
      logging.warn('Unknown arguments are removed from the options: %s',
                   self.removed_args)


class CrOSUpdateTrigger(object):
  """The class for CrOS auto-updater trigger.

  This class is used for running all CrOS auto-update trigger logic.
  """
  def __init__(self, host_name, build_name, static_dir, progress_tracker=None,
               log_file=None, au_tempdir=None, force_update=False,
               full_update=False, original_build=None, payload_filename=None,
               clobber_stateful=True):
    self.host_name = host_name
    self.build_name = build_name
    self.static_dir = static_dir
    self.progress_tracker = progress_tracker
    self.log_file = log_file
    self.au_tempdir = au_tempdir
    self.force_update = force_update
    self.full_update = full_update
    self.original_build = original_build
    self.payload_filename = payload_filename
    self.clobber_stateful = clobber_stateful

  def _WriteAUStatus(self, content):
    if self.progress_tracker:
      self.progress_tracker.WriteStatus(content)

  def _StatefulUpdate(self, cros_updater):
    """The detailed process in stateful update.

    Args:
      cros_updater: The CrOS auto updater for auto-update.
    """
    self._WriteAUStatus('pre-setup stateful update')
    cros_updater.PreSetupStatefulUpdate()
    self._WriteAUStatus('perform stateful update')
    cros_updater.UpdateStateful()
    self._WriteAUStatus('post-check stateful update')
    cros_updater.PostCheckStatefulUpdate()

  def _RootfsUpdate(self, cros_updater):
    """The detailed process in rootfs update.

    Args:
      cros_updater: The CrOS auto updater for auto-update.
    """
    self._WriteAUStatus('Check whether devserver can run before rootfs update')
    cros_updater.CheckDevserverRun()
    self._WriteAUStatus('transfer rootfs update package')
    cros_updater.TransferRootfsUpdate()
    self._WriteAUStatus('pre-setup rootfs update')
    cros_updater.PreSetupRootfsUpdate()
    self._WriteAUStatus('rootfs update')
    cros_updater.UpdateRootfs()
    self._WriteAUStatus('post-check rootfs update')
    cros_updater.PostCheckRootfsUpdate()

  def _GetOriginalPayloadDir(self):
    """Get the directory of original payload.

    Returns:
      The directory of original payload, whose format is like:
          'static/stable-channel/link/3428.210.0'
    """
    if self.original_build:
      return os.path.join(self.static_dir, '%s/%s' % (STABLE_BUILD_CHANNEL,
                                                      self.original_build))
    else:
      return None

  def TriggerAU(self):
    """Execute auto update for cros_host.

    The auto update includes 4 steps:
    1. if devserver cannot run, restore the stateful partition.
    2. if possible, do stateful update first, but never raise errors, except
       for timeout_util.TimeoutError caused by system.signal.
    3. If required or stateful_update fails, first do rootfs update, then do
       stateful_update.
    4. Post-check for the whole update.
    """
    try:
      with remote_access.ChromiumOSDeviceHandler(
          self.host_name, port=None,
          base_dir=CROS_PRESERVED_PATH,
          ping=False) as device:

        logging.debug('Remote device %s is connected', self.host_name)
        payload_dir = os.path.join(self.static_dir, self.build_name)
        original_payload_dir = self._GetOriginalPayloadDir()

        chromeos_AU = auto_updater.ChromiumOSUpdater(
            device, self.build_name, payload_dir,
            dev_dir=os.path.abspath(os.path.dirname(__file__)),
            tempdir=self.au_tempdir,
            log_file=self.log_file,
            original_payload_dir=original_payload_dir,
            yes=True,
            payload_filename=self.payload_filename,
            clobber_stateful=self.clobber_stateful)
        chromeos_AU.CheckPayloads()

        version_match = chromeos_AU.PreSetupCrOSUpdate()
        self._WriteAUStatus('Transfer Devserver/Stateful Update Package')
        chromeos_AU.TransferDevServerPackage()
        chromeos_AU.TransferStatefulUpdate()

        restore_stateful = chromeos_AU.CheckRestoreStateful()
        do_stateful_update = (not self.full_update) and (
            version_match and self.force_update)
        stateful_update_complete = False
        logging.debug('Start CrOS update process...')
        try:
          if restore_stateful:
            self._WriteAUStatus('Restore Stateful Partition')
            chromeos_AU.RestoreStateful()
            stateful_update_complete = True
          else:
            # Whether to execute stateful update depends on:
            # a. full_update=False: No full reimage is required.
            # b. The update version is matched to the current version, And
            #    force_update=True: Update is forced even if the version
            #    installed is the same.
            if do_stateful_update:
              self._StatefulUpdate(chromeos_AU)
              stateful_update_complete = True

        except timeout_util.TimeoutError:
          raise
        except Exception as e:
          logging.debug('Error happens in stateful update: %r', e)

        # Whether to execute rootfs update depends on:
        # a. stateful update is not completed, or completed by
        #    update action 'restore_stateful'.
        # b. force_update=True: Update is forced no matter what the current
        #    version is. Or, the update version is not matched to the current
        #    version.
        require_rootfs_update = self.force_update or (
            not chromeos_AU.CheckVersion())
        if (not (do_stateful_update and stateful_update_complete)
            and require_rootfs_update):
          self._RootfsUpdate(chromeos_AU)
          self._StatefulUpdate(chromeos_AU)

        self._WriteAUStatus('post-check for CrOS auto-update')
        chromeos_AU.PostCheckCrOSUpdate()
        self._WriteAUStatus(cros_update_progress.FINISHED)
    except Exception as e:
      logging.debug('Error happens in CrOS auto-update: %r', e)
      self._WriteAUStatus(CROS_ERROR_TEMPLATE % str(traceback.format_exc()))
      raise


def main():
  # Setting logging level
  logConfig = cros_update_logging.loggingConfig()
  logConfig.ConfigureLogging()

  # Create one cros_update_parser instance for parsing CrOS auto-update cmd.
  AU_parser = CrOSAUParser()
  try:
    AU_parser.ParseArgs()
  except Exception as e:
    logging.error('Error in Parsing Args: %r', e)
    raise

  if len(sys.argv) == 1:
    AU_parser.parser.print_help()
    sys.exit(1)

  options = AU_parser.options

  # Use process group id as the unique id in track and log files, since
  # os.setsid is executed before the current process is run.
  pid = os.getpid()
  pgid = os.getpgid(pid)

  # Setting log files for CrOS auto-update process.
  # Log file:  file to record every details of CrOS auto-update process.
  log_file = cros_update_progress.GetExecuteLogFile(options.host_name, pgid)
  logging.info('Writing executing logs into file: %s', log_file)
  logConfig.SetFileHandler(log_file)

  # Create a progress_tracker for tracking CrOS auto-update progress.
  progress_tracker = cros_update_progress.AUProgress(options.host_name, pgid)

  # Create a dir for temporarily storing devserver codes and logs.
  au_tempdir = cros_update_progress.GetAUTempDirectory(options.host_name, pgid)

  # Create cros_update instance to run CrOS auto-update.
  cros_updater_trigger = CrOSUpdateTrigger(
      options.host_name, options.build_name, options.static_dir,
      progress_tracker=progress_tracker,
      log_file=log_file,
      au_tempdir=au_tempdir,
      force_update=options.force_update,
      full_update=options.full_update,
      original_build=options.original_build,
      payload_filename=options.payload_filename,
      clobber_stateful=options.clobber_stateful)

  # Set timeout the cros-update process.
  try:
    with timeout_util.Timeout(CROS_UPDATE_TIMEOUT_MIN*60):
      cros_updater_trigger.TriggerAU()
  except timeout_util.TimeoutError as e:
    error_msg = ('%s. The CrOS auto-update process is timed out, thus will be '
                 'terminated' % str(e))
    progress_tracker.WriteStatus(CROS_ERROR_TEMPLATE % error_msg)


if __name__ == '__main__':
  main()
