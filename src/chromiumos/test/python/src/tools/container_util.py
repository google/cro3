# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility to tar Autotest and Tast artifacts from given path to given path."""

import fnmatch
import os
import pathlib
import sys


sys.path.insert(1, str(pathlib.Path(__file__).parent.resolve() / '../../'))

from src.tools import cmd_util  # noqa: E402


COMP_NONE = 0
COMP_GZIP = 1
COMP_BZIP2 = 2
COMP_XZ = 3


def _FindSourceRoot():
  """Try and find the root check out of the chromiumos tree"""
  source_root = path = os.path.realpath(
      os.path.join(os.path.abspath(__file__), '..', '..', '..'))
  while True:
    if os.path.isdir(os.path.join(path, '.repo')):
      return path
    elif path == '/':
      break
    path = os.path.dirname(path)
  return source_root


SOURCE_ROOT = _FindSourceRoot()


def FromChrootPath(chroot, file):
  return os.path.join(chroot, file)


def FromSysrootPath(sysroot, file):
  return os.path.join(sysroot, file)


def FindFilesMatching(pattern, target='./', cwd=os.curdir, exclude_dirs=[]):
  """Search the root directory recursively for matching filenames.

  The |target| and |cwd| args allow manipulating how the found paths are
  returned as well as specifying where the search needs to be executed.

  If our filesystem only has /path/to/example.txt, and our pattern is '*.txt':
  |target|='./', |cwd|='/path'  =>  ./to/example.txt
  |target|='to', |cwd|='/path'  =>  to/example.txt
  |target|='./', |cwd|='/path/to' =>  ./example.txt
  |target|='/path'        =>  /path/to/example.txt
  |target|='/path/to'       =>  /path/to/example.txt

  Args:
    pattern: the pattern used to match the filenames.
    target: the target directory to search.
    cwd: current working directory.
    exclude_dirs: Directories to not include when searching.

  Returns:
    A list of paths of the matched files.
  """
  assert cwd
  assert os.path.exists(cwd)

  # Backup the current working directory before changing it.
  old_cwd = os.getcwd()
  os.chdir(cwd)

  matches = []
  for directory, _, filenames in os.walk(target):
    if any(directory.startswith(e) for e in exclude_dirs):
      # Skip files in excluded directories.
      continue

    for filename in fnmatch.filter(filenames, pattern):
      matches.append(os.path.join(directory, filename))

  # Restore the working directory.
  os.chdir(old_cwd)

  return matches


class AutotestTarballBuilder(object):
  """Builds autotest tarballs for testing."""

  # Archive file names.
  _SERVER_PACKAGE_ARCHIVE = 'autotest_server_package.tar.bz2'

  # Directory within _SERVER_PACKAGE_ARCHIVE where Tast files needed to run
  # with Server-Side Packaging are stored.
  _TAST_SUBDIR = 'tast'

  # Tast files and directories to include in AUTOTEST_SERVER_PACKAGE relative
  # to the build root.
  _TAST_FILES = [
      'usr/bin/tast',  # Main Tast executable.
      'usr/bin/remote_test_runner',  # Runs remote tests.
      'usr/libexec/tast/bundles',  # Dir containing test bundles.
      'usr/share/tast/data',  # Dir containing test data.
      'etc/tast/vars',  # Secret variables.
  ]
  # Tast files and directories stored in the source code.
  _TAST_SOURCE_FILES = [
      'src/platform/tast/tools/run_tast.sh',  # Helper to run tast.
  ]

  def __init__(self,
               archive_basedir,
               output_directory,
               chroot_path,
               tko_only=False):
    """Init function.

    Args:
      archive_basedir (str): The base directory from which the archives
        will be created. This path should contain the `autotest`
        directory.
      output_directory (str): The directory where the archives will be
        written.
      chroot_path (str): Path to the chroot fs.
      tko_onky (bool): Flag to only bundle tko & required content.
    """
    self.archive_basedir = archive_basedir
    self.output_directory = output_directory
    self.chroot_path = chroot_path
    self.tko_only = tko_only

  def BuildFullAutotestandTastTarball(self):
    """Tar all needed Autotest & Tast files required by Docker Container.

    NOTE: This does not include autotest/packages, but will include all
    tests and client/deps.

    Returns:
      str|None - The path of the autotest server package tarball if
        created.
    """
    if not self.tko_only:
      tast_files, transforms = self._GetTastServerFilesAndTarTransforms()
    else:
      tast_files, transforms = [], []

    autotest_files = FindFilesMatching(
        '*',
        target='autotest',
        cwd=self.archive_basedir,
        exclude_dirs=('autotest/packages',))

    tarball = os.path.join(self.output_directory,
                           self._SERVER_PACKAGE_ARCHIVE)
    if self._BuildTarball(autotest_files + tast_files,
                          tarball,
                          extra_args=transforms):
      return tarball
    else:
      return None

  def _BuildTarball(self, input_list, tarball_path, extra_args=None):
    """Tar and zip files and directories from input_list to tarball_path.

    Args:
      input_list: A list of files and directories to be archived.
      tarball_path: Path of output tar archive file.
      extra_args: extra arguments to pass to CreateTarball.

    Returns:
      Return value of CreateTarball.
    """
    for pathname in input_list:
      if os.path.exists(os.path.join(self.archive_basedir, pathname)):
        break
    else:
      # If any of them exist we can create an archive, but if none
      # do then we need to stop. For now, since we either pass in a
      # handful of directories we don't necessarily check, or actually
      # search the filesystem for lots of files, this is far more
      # efficient than building out a list of files that do exist.
      return None
    compressor = COMP_BZIP2
    chroot = self.chroot_path

    return cmd_util.CreateTarball(tarball_path,
                                  self.archive_basedir,
                                  compression=compressor,
                                  chroot=chroot,
                                  inputs=input_list,
                                  extra_args=extra_args)

  def _GetTastServerFilesAndTarTransforms(self):
    """Return Tast server files and corresponding tar transform flags.

    The returned paths should be included in AUTOTEST_SERVER_PACKAGE. The
    --transform arguments should be passed to GNU tar to convert the paths
    to appropriate destinations in the tarball.

    Returns:
      (files, transforms), where files is a list of absolute paths to
        Tast server files/directories and transforms is a list of
        --transform arguments to pass to GNU tar when archiving those
        files.
    """
    files = []
    transforms = []

    for path in self._GetTastFiles():
      if not os.path.exists(path):
        continue

      files.append(path)
      dest = os.path.join(self._TAST_SUBDIR, os.path.basename(path))
      transforms.append('--transform=s|^%s|%s|' %
                        (os.path.relpath(path, '/'), dest))

    return files, transforms

  def _GetTastFiles(self):
    """Build out the paths to the tast files.

    Returns:
      list[str] - The paths to the files.
    """
    files = []
    files.extend(
        FromChrootPath(self.chroot_path, x) for x in self._TAST_FILES)

    for filename in self._TAST_SOURCE_FILES:
      files.append(os.path.join(SOURCE_ROOT, filename))

    return files
