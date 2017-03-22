#!/usr/bin/env python2

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Downloaders used to download artifacts and files from a given source."""

from __future__ import print_function

import collections
import glob
import os
import re
import shutil
import threading
from datetime import datetime

import build_artifact
import common_util
import log_util

# Make sure that chromite is available to import.
import setup_chromite # pylint: disable=unused-import

try:
  from chromite.lib import gs
except ImportError as e:
  gs = None

try:
  import android_build
except ImportError as e:
  # Ignore android_build import failure. This is to support devserver running
  # inside a ChromeOS device triggered by cros flash. Most ChromeOS test images
  # do not have google-api-python-client module and they don't need to support
  # Android updating, therefore, ignore the import failure here.
  android_build = None


class DownloaderException(Exception):
  """Exception that aggregates all exceptions raised during async download.

  Exceptions could be raised in artifact.Process method, and saved to files.
  When caller calls IsStaged to check the downloading progress, devserver can
  retrieve the persisted exceptions from the files, wrap them into a
  DownloaderException, and raise it.
  """
  def __init__(self, exceptions):
    """Initialize a DownloaderException instance with a list of exceptions.

    Args:
      exceptions: Exceptions raised when downloading artifacts.
    """
    message = 'Exceptions were raised when downloading artifacts.'
    Exception.__init__(self, message)
    self.exceptions = exceptions

  def __repr__(self):
    return self.__str__()

  def __str__(self):
    """Return a custom exception message with all exceptions merged."""
    return '--------\n'.join([str(exception) for exception in self.exceptions])

class Downloader(log_util.Loggable):
  """Downloader of images to the devsever.

  This is the base class for different types of downloaders, including
  GoogleStorageDownloader, LocalDownloader and AndroidBuildDownloader.

  Given a URL to a build on the archive server:
    - Caches that build and the given artifacts onto the devserver.
    - May also initiate caching of related artifacts in the background.

  Private class members:
    static_dir: local filesystem directory to store all artifacts.
    build_dir: the local filesystem directory to store artifacts for the given
      build based on the remote source.

  Public methods must be overridden:
    Wait: Verifies the local artifact exists and returns the appropriate names.
    Fetch: Downloads artifact from given source to a local directory.
    DescribeSource: Gets the source of the download, e.g., a url to GS.
  """

  # This filename must be kept in sync with clean_staged_images.py
  _TIMESTAMP_FILENAME = 'staged.timestamp'

  def __init__(self, static_dir, build_dir, build):
    super(Downloader, self).__init__()
    self._static_dir = static_dir
    self._build_dir = build_dir
    self._build = build

  def GetBuildDir(self):
    """Returns the path to where the artifacts will be staged."""
    return self._build_dir

  def GetBuild(self):
    """Returns the path to where the artifacts will be staged."""
    return self._build

  @staticmethod
  def TouchTimestampForStaged(directory_path):
    file_name = os.path.join(directory_path, Downloader._TIMESTAMP_FILENAME)
    # Easiest python version of |touch file_name|
    with file(file_name, 'a'):
      os.utime(file_name, None)

  @staticmethod
  def _TryRemoveStageDir(directory_path):
    """If download failed, try to remove the stage dir.

    If the download attempt failed (ArtifactDownloadError) and staged.timestamp
    is the only file in that directory. The build could be non-existing, and
    the directory should be removed.

    Args:
      directory_path: directory used to stage the image.
    """
    file_name = os.path.join(directory_path, Downloader._TIMESTAMP_FILENAME)
    if os.path.exists(file_name) and len(os.listdir(directory_path)) == 1:
      os.remove(file_name)
      os.rmdir(directory_path)

  def ListBuildDir(self):
    """List the files in the build directory.

    Only lists files a single level into the build directory. Includes
    timestamp information in the listing.

    Returns:
      A string with information about the files in the build directory.
      None if the build directory doesn't exist.

    Raises:
      build_artifact.ArtifactDownloadError: If the build_dir path exists
      but is not a directory.
    """
    if not os.path.exists(self._build_dir):
      return None
    if not os.path.isdir(self._build_dir):
      raise build_artifact.ArtifactDownloadError(
          'Artifacts %s improperly staged to build_dir path %s. The path is '
          'not a directory.' % (self._archive_url, self._build_dir))

    ls_format = collections.namedtuple(
        'ls', ['name', 'accessed', 'modified', 'size'])
    output_format = ('Name: %(name)s Accessed: %(accessed)s '
                     'Modified: %(modified)s Size: %(size)s bytes.\n')

    build_dir_info = 'Listing contents of :%s \n' % self._build_dir
    for file_name in os.listdir(self._build_dir):
      file_path = os.path.join(self._build_dir, file_name)
      file_info = os.stat(file_path)
      ls_info = ls_format(file_path,
                          datetime.fromtimestamp(file_info.st_atime),
                          datetime.fromtimestamp(file_info.st_mtime),
                          file_info.st_size)
      build_dir_info += output_format % ls_info._asdict()
    return build_dir_info

  def Download(self, factory, async=False):
    """Downloads and caches the |artifacts|.

    Downloads and caches the |artifacts|. Returns once these are present on the
    devserver. A call to this will attempt to cache non-specified artifacts in
    the background following the principle of spatial locality.

    Args:
     factory: The artifact factory.
     async: If True, return without waiting for download to complete.

    Raises:
      build_artifact.ArtifactDownloadError: If failed to download the artifact.
    """
    common_util.MkDirP(self._build_dir)

    # We are doing some work on this build -- let's touch it to indicate that
    # we shouldn't be cleaning it up anytime soon.
    Downloader.TouchTimestampForStaged(self._build_dir)

    # Create factory to create build_artifacts from artifact names.
    background_artifacts = factory.OptionalArtifacts()
    if background_artifacts:
      self._DownloadArtifactsInBackground(background_artifacts)

    required_artifacts = factory.RequiredArtifacts()
    str_repr = [str(a) for a in required_artifacts]
    self._Log('Downloading artifacts %s.', ' '.join(str_repr))

    if async:
      self._DownloadArtifactsInBackground(required_artifacts)
    else:
      self._DownloadArtifactsSerially(required_artifacts, no_wait=True)

  def IsStaged(self, factory):
    """Check if all artifacts have been downloaded.

    Args:
      factory: An instance of BaseArtifactFactory to be used to check if desired
               artifacts or files are staged.

    Returns:
      True if all artifacts are staged.

    Raises:
      DownloaderException: A wrapper for exceptions raised by any artifact when
                           calling Process.
    """
    required_artifacts = factory.RequiredArtifacts()
    exceptions = [artifact.GetException() for artifact in required_artifacts if
                  artifact.GetException()]
    if exceptions:
      raise DownloaderException(exceptions)

    return all([artifact.ArtifactStaged() for artifact in required_artifacts])

  def _DownloadArtifactsSerially(self, artifacts, no_wait):
    """Simple function to download all the given artifacts serially.

    Args:
      artifacts: A list of build_artifact.BuildArtifact instances to
                 download.
      no_wait: If True, don't block waiting for artifact to exist if we
               fail to immediately find it.

    Raises:
      build_artifact.ArtifactDownloadError: If we failed to download the
                                            artifact.
    """
    try:
      for artifact in artifacts:
        artifact.Process(self, no_wait)
    except build_artifact.ArtifactDownloadError:
      Downloader._TryRemoveStageDir(self._build_dir)
      raise

  def _DownloadArtifactsInBackground(self, artifacts):
    """Downloads |artifacts| in the background.

    Downloads |artifacts| in the background. As these are backgrounded
    artifacts, they are done best effort and may not exist.

    Args:
      artifacts: List of build_artifact.BuildArtifact instances to download.
    """
    self._Log('Invoking background download of artifacts for %r', artifacts)
    thread = threading.Thread(target=self._DownloadArtifactsSerially,
                              args=(artifacts, False))
    thread.start()

  def Wait(self, name, is_regex_name, timeout):
    """Waits for artifact to exist and returns the appropriate names.

    Args:
      name: Name to look at.
      is_regex_name: True if the name is a regex pattern.
      timeout: How long to wait for the artifact to become available.

    Returns:
      A list of names that match.
    """
    raise NotImplementedError()

  def Fetch(self, remote_name, local_path):
    """Downloads artifact from given source to a local directory.

    Args:
      remote_name: Remote name of the file to fetch.
      local_path: Local path to the folder to store fetched file.

    Returns:
      The path to fetched file.
    """
    raise NotImplementedError()

  def DescribeSource(self):
    """Gets the source of the download, e.g., a url to GS."""
    raise NotImplementedError()


class GoogleStorageDownloader(Downloader):
  """Downloader of images to the devserver from Google Storage.

  Given a URL to a build on the archive server:
    - Caches that build and the given artifacts onto the devserver.
    - May also initiate caching of related artifacts in the background.

  This is intended to be used with ChromeOS.

  Private class members:
    archive_url: Google Storage URL to download build artifacts from.
  """

  def __init__(self, static_dir, archive_url):
    # The archive_url is of the form gs://server/[some_path/target]/...]/build
    # This function discards 'gs://server/' and extracts the [some_path/target]
    # as rel_path and the build as build.
    sub_url = archive_url.partition('://')[2]
    split_sub_url = sub_url.split('/')
    rel_path = '/'.join(split_sub_url[1:-1])
    build = split_sub_url[-1]
    build_dir = os.path.join(static_dir, rel_path, build)

    super(GoogleStorageDownloader, self).__init__(static_dir, build_dir, build)

    self._archive_url = archive_url

    if common_util.IsRunningOnMoblab():
      self._ctx = gs.GSContext(cache_user='chronos') if gs else None
    else:
      self._ctx = gs.GSContext() if gs else None

  def Wait(self, name, is_regex_name, timeout):
    """Waits for artifact to exist and returns the appropriate names.

    Args:
      name: Name to look at.
      is_regex_name: True if the name is a regex pattern.
      timeout: How long to wait for the artifact to become available.

    Returns:
      A list of names that match.

    Raises:
      ArtifactDownloadError: An error occurred when obtaining artifact.
    """
    names = self._ctx.GetGsNamesWithWait(
        name, self._archive_url, timeout=timeout,
        is_regex_pattern=is_regex_name)
    if not names:
      raise build_artifact.ArtifactDownloadError(
          'Could not find %s in Google Storage at %s' %
          (name, self._archive_url))
    return names

  def Fetch(self, remote_name, local_path):
    """Downloads artifact from Google Storage to a local directory."""
    install_path = os.path.join(local_path, remote_name)
    gs_path = '/'.join([self._archive_url, remote_name])
    self._ctx.Copy(gs_path, local_path)
    return install_path

  def DescribeSource(self):
    return self._archive_url


class LocalDownloader(Downloader):
  """Downloader of images to the devserver from local storage.

  Given a local path:
    - Caches that build and the given artifacts onto the devserver.
    - May also initiate caching of related artifacts in the background.

  Private class members:
    archive_params: parameters for where to download build artifacts from.
  """

  def __init__(self, static_dir, source_path):
    # The local path is of the form /{path to static dir}/{rel_path}/{build}.
    # local_path must be a subpath of the static directory.
    self.source_path = source_path
    rel_path = os.path.basename(os.path.dirname(source_path))
    build = os.path.basename(source_path)
    build_dir = os.path.join(static_dir, rel_path, build)

    super(LocalDownloader, self).__init__(static_dir, build_dir, build)

  def Wait(self, name, is_regex_name, timeout):
    """Verifies the local artifact exists and returns the appropriate names.

    Args:
      name: Name to look at.
      is_regex_name: True if the name is a regex pattern.
      timeout: How long to wait for the artifact to become available.

    Returns:
      A list of names that match.

    Raises:
      ArtifactDownloadError: An error occurred when obtaining artifact.
    """
    local_path = os.path.join(self.source_path, name)
    if is_regex_name:
      filter_re = re.compile(name)
      for filename in os.listdir(self.source_path):
        if filter_re.match(filename):
          return [filename]
    else:
      glob_search = glob.glob(local_path)
      if glob_search and len(glob_search) == 1:
        return [os.path.basename(glob_search[0])]
    raise build_artifact.ArtifactDownloadError('Artifact not found.')

  def Fetch(self, remote_name, local_path):
    """Downloads artifact from Google Storage to a local directory."""
    install_path = os.path.join(local_path, remote_name)
    # It's a local path so just copy it into the staged directory.
    shutil.copyfile(os.path.join(self.source_path, remote_name),
                    install_path)
    return install_path

  def DescribeSource(self):
    return self.source_path


class AndroidBuildDownloader(Downloader):
  """Downloader of images to the devserver from Android's build server."""

  def __init__(self, static_dir, branch, build_id, target):
    """Initialize AndroidBuildDownloader.

    Args:
      static_dir: Root directory to store the build.
      branch: Branch for the build. Download will always verify if the given
              build id is for the branch.
      build_id: Build id of the Android build, e.g., 2155602.
      target: Target of the Android build, e.g., shamu-userdebug.
    """
    build = '%s/%s/%s' % (branch, target, build_id)
    build_dir = os.path.join(static_dir, '', build)

    self.branch = branch
    self.build_id = build_id
    self.target = target

    super(AndroidBuildDownloader, self).__init__(static_dir, build_dir, build)

  def Wait(self, name, is_regex_name, timeout):
    """Verifies the local artifact exists and returns the appropriate names.

    Args:
      name: Name to look at.
      is_regex_name: True if the name is a regex pattern.
      timeout: How long to wait for the artifact to become available.

    Returns:
      A list of names that match.

    Raises:
      ArtifactDownloadError: An error occurred when obtaining artifact.
    """
    artifacts = android_build.BuildAccessor.GetArtifacts(
        branch=self.branch, build_id=self.build_id, target=self.target)

    names = []
    for artifact_name in [a['name'] for a in artifacts]:
      match = (re.match(name, artifact_name) if is_regex_name
               else name == artifact_name)
      if match:
        names.append(artifact_name)

    if not names:
      raise build_artifact.ArtifactDownloadError(
          'No artifact found with given name: %s for %s-%s' %
          (name, self.target, self.build_id))

    return names

  def Fetch(self, remote_name, local_path):
    """Downloads artifact from Android's build server to a local directory."""
    dest_file = os.path.join(local_path, remote_name)
    android_build.BuildAccessor.Download(
        branch=self.branch, build_id=self.build_id, target=self.target,
        resource_id=remote_name, dest_file=dest_file)
    return dest_file

  def DescribeSource(self):
    return '%s/%s/%s/%s' % (android_build.DEFAULT_BUILDER, self.branch,
                            self.target, self.build_id)
