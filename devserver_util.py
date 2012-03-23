# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helper class for interacting with the Dev Server."""

import cherrypy
import distutils.version
import errno
import os
import shutil
import subprocess


GSUTIL_ATTEMPTS = 5
AU_BASE = 'au'
NTON_DIR_SUFFIX = '_nton'
MTON_DIR_SUFFIX = '_mton'
ROOT_UPDATE = 'update.gz'
STATEFUL_UPDATE = 'stateful.tgz'
TEST_IMAGE = 'chromiumos_test_image.bin'
AUTOTEST_PACKAGE = 'autotest.tar.bz2'
DEV_BUILD_PREFIX = 'dev'


class DevServerUtilError(Exception):
  """Exception classes used by this module."""
  pass


def ParsePayloadList(payload_list):
  """Parse and return the full/delta payload URLs.

  Args:
    payload_list: A list of Google Storage URLs.

  Returns:
    Tuple of 3 payloads URLs: (full, nton, mton).

  Raises:
    DevServerUtilError: If payloads missing or invalid.
  """
  full_payload_url = None
  mton_payload_url = None
  nton_payload_url = None
  for payload in payload_list:
    if '_full_' in payload:
      full_payload_url = payload
    elif '_delta_' in payload:
      # e.g. chromeos_{from_version}_{to_version}_x86-generic_delta_dev.bin
      from_version, to_version = payload.rsplit('/', 1)[1].split('_')[1:3]
      if from_version == to_version:
        nton_payload_url = payload
      else:
        mton_payload_url = payload

  if not full_payload_url or not nton_payload_url or not mton_payload_url:
    raise DevServerUtilError(
        'Payloads are missing or have unexpected name formats.', payload_list)

  return full_payload_url, nton_payload_url, mton_payload_url


def DownloadBuildFromGS(staging_dir, archive_url, build):
  """Downloads the specified build from Google Storage into a temp directory.

  The archive is expected to contain stateful.tgz, autotest.tar.bz2, and three
  payloads: full, N-1->N, and N->N. gsutil is used to download the file.
  gsutil must be in the path and should have required credentials.

  Args:
    staging_dir: Temp directory containing payloads and autotest packages.
    archive_url: Google Storage path to the build directory.
        e.g. gs://chromeos-image-archive/x86-generic/R17-1208.0.0-a1-b338.
    build: Full build string to look for; e.g. R17-1208.0.0-a1-b338.

  Raises:
    DevServerUtilError: If any steps in the process fail to complete.
  """
  def GSUtilRun(cmd, err_msg):
    """Runs a GSUTIL command up to GSUTIL_ATTEMPTS number of times.

    Raises:
      subprocess.CalledProcessError if all attempt to run gsutil cmd fails.
    """
    proc = None
    for _attempt in range(GSUTIL_ATTEMPTS):
      proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
      stdout, _stderr = proc.communicate()
      if proc.returncode == 0:
        return stdout
    else:
      raise DevServerUtilError('%s GSUTIL cmd %s failed with return code %d' % (
          err_msg, cmd, proc.returncode))

  # Get a list of payloads from Google Storage.
  cmd = 'gsutil ls %s/*.bin' % archive_url
  msg = 'Failed to get a list of payloads.'
  stdout = GSUtilRun(cmd, msg)

  payload_list = stdout.splitlines()
  full_payload_url, nton_payload_url, mton_payload_url = (
      ParsePayloadList(payload_list))

  # Create temp directories for payloads.
  nton_payload_dir = os.path.join(staging_dir, AU_BASE, build + NTON_DIR_SUFFIX)
  os.makedirs(nton_payload_dir)
  mton_payload_dir = os.path.join(staging_dir, AU_BASE, build + MTON_DIR_SUFFIX)
  os.mkdir(mton_payload_dir)

  # Download build components into respective directories.
  src = [full_payload_url,
         nton_payload_url,
         mton_payload_url,
         archive_url + '/' + STATEFUL_UPDATE,
         archive_url + '/' + AUTOTEST_PACKAGE]
  dst = [os.path.join(staging_dir, ROOT_UPDATE),
         os.path.join(nton_payload_dir, ROOT_UPDATE),
         os.path.join(mton_payload_dir, ROOT_UPDATE),
         staging_dir,
         staging_dir]
  for src, dest in zip(src, dst):
    cmd = 'gsutil cp %s %s' % (src, dest)
    msg = 'Failed to download "%s".' % src
    GSUtilRun(cmd, msg)


def InstallBuild(staging_dir, build_dir):
  """Installs various build components from staging directory.

  Specifically, the following components are installed:
    - update.gz
    - stateful.tgz
    - chromiumos_test_image.bin
    - The entire contents of the au directory. Symlinks are generated for each
      au payload as well.
    - Contents of autotest-pkgs directory.
    - Control files from autotest/server/{tests, site_tests}

  Args:
    staging_dir: Temp directory containing payloads and autotest packages.
    build_dir: Directory to install build components into.
  """
  install_list = [ROOT_UPDATE, STATEFUL_UPDATE]

  # Create blank chromiumos_test_image.bin. Otherwise the Dev Server will
  # try to rebuild it unnecessarily.
  test_image = os.path.join(build_dir, TEST_IMAGE)
  open(test_image, 'a').close()

  # Install AU payloads.
  au_path = os.path.join(staging_dir, AU_BASE)
  install_list.append(AU_BASE)
  # For each AU payload, setup symlinks to the main payloads.
  cwd = os.getcwd()
  for au in os.listdir(au_path):
    os.chdir(os.path.join(au_path, au))
    os.symlink(os.path.join(os.pardir, os.pardir, TEST_IMAGE), TEST_IMAGE)
    os.symlink(os.path.join(os.pardir, os.pardir, STATEFUL_UPDATE),
               STATEFUL_UPDATE)
    os.chdir(cwd)

  for component in install_list:
    shutil.move(os.path.join(staging_dir, component), build_dir)

  shutil.move(os.path.join(staging_dir, 'autotest'),
              os.path.join(build_dir, 'autotest'))


def PrepareAutotestPkgs(staging_dir):
  """Create autotest client packages inside staging_dir.

  Args:
    staging_dir: Temp directory containing payloads and autotest packages.

  Raises:
    DevServerUtilError: If any steps in the process fail to complete.
  """
  cmd = ('tar xf %s --use-compress-prog=pbzip2 --directory=%s' %
         (os.path.join(staging_dir, AUTOTEST_PACKAGE), staging_dir))
  msg = 'Failed to extract autotest.tar.bz2 ! Is pbzip2 installed?'
  try:
    subprocess.check_call(cmd, shell=True)
  except subprocess.CalledProcessError, e:
    raise DevServerUtilError('%s %s' % (msg, e))

  # Use the root of Autotest
  autotest_pkgs_dir = os.path.join(staging_dir, 'autotest', 'packages')
  if not os.path.exists(autotest_pkgs_dir):
    os.makedirs(autotest_pkgs_dir)

  if not os.path.exists(os.path.join(autotest_pkgs_dir, 'packages.checksum')):
    cmd_list = ['autotest/utils/packager.py',
                'upload', '--repository', autotest_pkgs_dir, '--all']
    msg = 'Failed to create autotest packages!'
    try:
      subprocess.check_call(' '.join(cmd_list), cwd=staging_dir, shell=True)
    except subprocess.CalledProcessError, e:
      raise DevServerUtilError('%s %s' % (msg, e))
  else:
    cherrypy.log('Using pre-generated packages from autotest', 'DEVSERVER_UTIL')

  # TODO(scottz): Remove after we have moved away from the old test_scheduler
  # code.
  cmd = 'cp %s/* %s' % (autotest_pkgs_dir,
                        os.path.join(staging_dir, 'autotest'))
  subprocess.check_call(cmd, shell=True)


def SafeSandboxAccess(static_dir, path):
  """Verify that the path is in static_dir.

  Args:
    static_dir: Directory where builds are served from.
    path: Path to verify.

  Returns:
    True if path is in static_dir, False otherwise
  """
  static_dir = os.path.realpath(static_dir)
  path = os.path.realpath(path)
  return (path.startswith(static_dir) and path != static_dir)


def AcquireLock(static_dir, tag):
  """Acquires a lock for a given tag.

  Creates a directory for the specified tag, telling other
  components the resource/task represented by the tag is unavailable.

  Args:
    static_dir: Directory where builds are served from.
    tag: Unique resource/task identifier. Use '/' for nested tags.

  Returns:
    Path to the created directory or None if creation failed.

  Raises:
    DevServerUtilError: If lock can't be acquired.
  """
  build_dir = os.path.join(static_dir, tag)
  if not SafeSandboxAccess(static_dir, build_dir):
    raise DevServerUtilError('Invaid tag "%s".' % tag)

  try:
    os.makedirs(build_dir)
  except OSError, e:
    if e.errno == errno.EEXIST:
      raise DevServerUtilError(str(e))
    else:
      raise

  return build_dir


def ReleaseLock(static_dir, tag):
  """Releases the lock for a given tag. Removes lock directory content.

  Args:
    static_dir: Directory where builds are served from.
    tag: Unique resource/task identifier. Use '/' for nested tags.

  Raises:
    DevServerUtilError: If lock can't be released.
  """
  build_dir = os.path.join(static_dir, tag)
  if not SafeSandboxAccess(static_dir, build_dir):
    raise DevServerUtilError('Invaid tag "%s".' % tag)

  shutil.rmtree(build_dir)


def FindMatchingBoards(static_dir, board):
  """Returns a list of boards given a partial board name.

  Args:
    static_dir: Directory where builds are served from.
    board: Partial board name for this build; e.g. x86-generic.

  Returns:
    Returns a list of boards given a partial board.
  """
  return [brd for brd in os.listdir(static_dir) if board in brd]


def FindMatchingBuilds(static_dir, board, build):
  """Returns a list of matching builds given a board and partial build.

  Args:
    static_dir: Directory where builds are served from.
    board: Partial board name for this build; e.g. x86-generic-release.
    build: Partial build string to look for; e.g. R17-1234.

  Returns:
    Returns a list of (board, build) tuples given a partial board and build.
  """
  matches = []
  for brd in FindMatchingBoards(static_dir, board):
    a = [(brd, bld) for bld in
         os.listdir(os.path.join(static_dir, brd)) if build in bld]
    matches.extend(a)
  return matches


def GetLatestBuildVersion(static_dir, target, milestone=None):
  """Retrieves the latest build version for a given board.

  Args:
    static_dir: Directory where builds are served from.
    target: The build target, typically a combination of the board and the
        type of build e.g. x86-mario-release.
    milestone: For latest build set to None, for builds only in a specific
        milestone set to a str of format Rxx (e.g. R16). Default: None.

  Returns:
    If latest found, a full build string is returned e.g. R17-1234.0.0-a1-b983.
    If no latest is found for some reason or another a '' string is returned.

  Raises:
    DevServerUtilError: If for some reason the latest build cannot be
        deteremined, this could be due to the dir not existing or no builds
        being present after filtering on milestone.
  """
  target_path = os.path.join(static_dir, target)
  if not os.path.isdir(target_path):
    raise DevServerUtilError('Cannot find path %s' % target_path)

  builds = [distutils.version.LooseVersion(build) for build in
            os.listdir(target_path)]

  if milestone and builds:
    # Check if milestone Rxx is in the string representation of the build.
    builds = filter(lambda x: milestone.upper() in str(x), builds)

  if not builds:
    raise DevServerUtilError('Could not determine build for %s' % target)

  return str(max(builds))


def CloneBuild(static_dir, board, build, tag, force=False):
  """Clone an official build into the developer sandbox.

  Developer sandbox directory must already exist.

  Args:
    static_dir: Directory where builds are served from.
    board: Fully qualified board name; e.g. x86-generic-release.
    build: Fully qualified build string; e.g. R17-1234.0.0-a1-b983.
    tag: Unique resource/task identifier. Use '/' for nested tags.
    force: Force re-creation of build_dir even if it already exists.

  Returns:
    The path to the new build.
  """
  # Create the developer build directory.
  dev_static_dir = os.path.join(static_dir, DEV_BUILD_PREFIX)
  dev_build_dir = os.path.join(dev_static_dir, tag)
  official_build_dir = os.path.join(static_dir, board, build)
  cherrypy.log('Cloning %s -> %s' % (official_build_dir, dev_build_dir),
               'DEVSERVER_UTIL')
  dev_build_exists = False
  try:
    AcquireLock(dev_static_dir, tag)
  except DevServerUtilError:
    dev_build_exists = True
    if force:
      dev_build_exists = False
      ReleaseLock(dev_static_dir, tag)
      AcquireLock(dev_static_dir, tag)

  # Make a copy of the official build, only take necessary files.
  if not dev_build_exists:
    copy_list = [TEST_IMAGE, ROOT_UPDATE, STATEFUL_UPDATE]
    for f in copy_list:
      shutil.copy(os.path.join(official_build_dir, f), dev_build_dir)

  return dev_build_dir


def GetControlFile(static_dir, build, control_path):
  """Attempts to pull the requested control file from the Dev Server.

  Args:
    static_dir: Directory where builds are served from.
    build: Fully qualified build string; e.g. R17-1234.0.0-a1-b983.
    control_path: Path to control file on Dev Server relative to Autotest root.

  Raises:
    DevServerUtilError: If lock can't be acquired.

  Returns:
    Content of the requested control file.
  """
  # Be forgiving if the user passes in the control_path with a leading /
  control_path = control_path.lstrip('/')
  control_path = os.path.join(static_dir, build, 'autotest',
                              control_path)
  if not SafeSandboxAccess(static_dir, control_path):
    raise DevServerUtilError('Invaid control file "%s".' % control_path)

  if not os.path.exists(control_path):
    # TODO(scottz): Come up with some sort of error mechanism.
    # crosbug.com/25040
    return 'Unknown control path %s' % control_path

  with open(control_path, 'r') as control_file:
    return control_file.read()


def GetControlFileList(static_dir, build):
  """List all control|control. files in the specified board/build path.

  Args:
    static_dir: Directory where builds are served from.
    build: Fully qualified build string; e.g. R17-1234.0.0-a1-b983.

  Raises:
    DevServerUtilError: If path is outside of sandbox.

  Returns:
    String of each file separated by a newline.
  """
  autotest_dir = os.path.join(static_dir, build, 'autotest/')
  if not SafeSandboxAccess(static_dir, autotest_dir):
    raise DevServerUtilError('Autotest dir not in sandbox "%s".' % autotest_dir)

  control_files = set()
  if not os.path.exists(autotest_dir):
    # TODO(scottz): Come up with some sort of error mechanism.
    # crosbug.com/25040
    return 'Unknown build path %s' % autotest_dir

  for entry in os.walk(autotest_dir):
    dir_path, _, files = entry
    for file_entry in files:
      if file_entry.startswith('control.') or file_entry == 'control':
        control_files.add(os.path.join(dir_path,
                                       file_entry).replace(autotest_dir, ''))

  return '\n'.join(control_files)


def ListAutoupdateTargets(static_dir, board, build):
  """Returns a list of autoupdate test targets for the given board, build.

  Args:
    static_dir: Directory where builds are served from.
    board: Fully qualified board name; e.g. x86-generic-release.
    build: Fully qualified build string; e.g. R17-1234.0.0-a1-b983.

  Returns:
    List of autoupdate test targets; e.g. ['0.14.747.0-r2bf8859c-b2927_nton']
  """
  return os.listdir(os.path.join(static_dir, board, build, AU_BASE))
