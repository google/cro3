# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import threading

import build_artifact
import common_util
import log_util


class DownloaderException(Exception):
  """Exception that aggregates all exceptions raised during async download.

  Exceptions could be raised in artifact.Process method, and saved to files.
  When caller calls IsStaged to check the downloading progress, devserver can
  retrieve the persisted exceptions from the files, wrap them into a
  DownloaderException, and raise it.
  """
  def __init__(self, exceptions):
    """Initialize a DownloaderException instance with a list of exceptions.

    @param exceptions: Exceptions raised when downloading artifacts.
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

  Given a URL to a build on the archive server:
    - Caches that build and the given artifacts onto the devserver.
    - May also initiate caching of related artifacts in the background.

  Private class members:
    archive_url: a URL where to download build artifacts from.
    static_dir: local filesystem directory to store all artifacts.
    build_dir: the local filesystem directory to store artifacts for the given
      build defined by the archive_url.
  """

  # This filename must be kept in sync with clean_staged_images.py
  _TIMESTAMP_FILENAME = 'staged.timestamp'

  def __init__(self, static_dir, archive_url):
    super(Downloader, self).__init__()
    self._archive_url = archive_url
    self._static_dir = static_dir
    self._build_dir = Downloader.GetBuildDir(static_dir, archive_url)

  @staticmethod
  def ParseUrl(archive_url):
    """Parses archive_url into rel_path and build.

    Parses archive_url into rel_path and build e.g.
    gs://chromeos-image-archive/{rel_path}/{build}.

    Args:
      archive_url: a URL at which build artifacts are archived.

    Returns:
      A tuple of (build relative path, short build name)
    """
    # The archive_url is of the form gs://server/[some_path/target]/...]/build
    # This function discards 'gs://server/' and extracts the [some_path/target]
    # as rel_path and the build as build.
    sub_url = archive_url.partition('://')[2]
    split_sub_url = sub_url.split('/')
    rel_path = '/'.join(split_sub_url[1:-1])
    build = split_sub_url[-1]
    return rel_path, build

  @staticmethod
  def GetBuildDir(static_dir, archive_url):
    """Returns the path to where the artifacts will be staged.

    Args:
      static_dir: The base static dir that will be used.
      archive_url: The gs path to the archive url.
    """
    # Parse archive_url into rel_path (contains the build target) and
    # build e.g. gs://chromeos-image-archive/{rel_path}/{build}.
    rel_path, build = Downloader.ParseUrl(archive_url)
    return os.path.join(static_dir, rel_path, build)

  @staticmethod
  def _TouchTimestampForStaged(directory_path):
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

    @param directory_path: directory used to stage the image.

    """
    file_name = os.path.join(directory_path, Downloader._TIMESTAMP_FILENAME)
    if os.path.exists(file_name) and len(os.listdir(directory_path)) == 1:
      os.remove(file_name)
      os.rmdir(directory_path)

  def Download(self, artifacts, files, async=False):
    """Downloads and caches the |artifacts|.

    Downloads and caches the |artifacts|. Returns once these
    are present on the devserver. A call to this will attempt to cache
    non-specified artifacts in the background following the principle of
    spatial locality.

    Args:
      artifacts: A list of artifact names that correspond to
                 artifacts defined in artifact_info.py to stage.
     files: A list of filenames to stage from an archive_url.
     async: If True, return without waiting for download to complete.

    Raises:
      build_artifact.ArtifactDownloadError: If failed to download the artifact.

    """
    common_util.MkDirP(self._build_dir)

    # We are doing some work on this build -- let's touch it to indicate that
    # we shouldn't be cleaning it up anytime soon.
    Downloader._TouchTimestampForStaged(self._build_dir)

    # Create factory to create build_artifacts from artifact names.
    build = self.ParseUrl(self._archive_url)[1]
    factory = build_artifact.ArtifactFactory(
        self._build_dir, self._archive_url, artifacts, files,
        build)
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

  def IsStaged(self, artifacts, files):
    """Check if all artifacts have been downloaded.

    artifacts: A list of artifact names that correspond to
               artifacts defined in artifact_info.py to stage.
    files: A list of filenames to stage from an archive_url.
    @returns: True if all artifacts are staged.
    @raise exception: that was raised by any artifact when calling Process.

    """
    # Create factory to create build_artifacts from artifact names.
    build = self.ParseUrl(self._archive_url)[1]
    factory = build_artifact.ArtifactFactory(
        self._build_dir, self._archive_url, artifacts, files, build)
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
        artifact.Process(no_wait)
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
