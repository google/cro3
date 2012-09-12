#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import Queue
import cherrypy
import os
import shutil
import tempfile
import threading

import devserver_util


class Downloader(object):
  """Download images to the devsever.

  Given a URL to a build on the archive server:

    - Determine if the build already exists.
    - Download and extract the build to a staging directory.
    - Package autotest tests.
    - Install components to static dir.
  """

  _LOG_TAG = 'DOWNLOAD'
  # This filename must be kept in sync with clean_staged_images.py
  _TIMESTAMP_FILENAME = 'staged.timestamp'

  def __init__(self, static_dir):
    self._static_dir = static_dir
    self._build_dir = None
    self._staging_dir = None
    self._status_queue = Queue.Queue(maxsize=1)
    self._lock_tag = None

  @staticmethod
  def ParseUrl(archive_url):
    """Parse archive_url into rel_path and short_build
    e.g. gs://chromeos-image-archive/{rel_path}/{short_build}

    @param archive_url: a URL at which build artifacts are archived.
    @return a tuple of (build relative path, short build name)
    """
    # The archive_url is of the form gs://server/[some_path/target]/...]/build
    # This function discards 'gs://server/' and extracts the [some_path/target]
    # as rel_path and the build as short_build.
    sub_url = archive_url.partition('://')[2]
    split_sub_url = sub_url.split('/')
    rel_path = '/'.join(split_sub_url[1:-1])
    short_build = split_sub_url[-1]
    return rel_path, short_build

  @staticmethod
  def GenerateLockTag(rel_path, short_build):
    """Generate a name for a lock scoped to this rel_path/build pair.

    @param rel_path: the relative path for the build.
    @param short_build: short build name
    @return a name to use with AcquireLock that will scope the lock.
    """
    return '/'.join([rel_path, short_build])

  @staticmethod
  def _TouchTimestampForStaged(directory_path):
    file_name = os.path.join(directory_path, Downloader._TIMESTAMP_FILENAME)
    # Easiest python version of |touch file_name|
    with file(file_name, 'a'):
      os.utime(file_name, None)

  @staticmethod
  def BuildStaged(archive_url, static_dir):
    """Returns True if the build is already staged."""
    rel_path, short_build = Downloader.ParseUrl(archive_url)
    sub_directory = Downloader.GenerateLockTag(rel_path, short_build)
    directory_path = os.path.join(static_dir, sub_directory)
    exists = os.path.isdir(directory_path)
    # If the build exists, then touch the timestamp to tell
    # clean_stages_images.py that we're using this build.
    if exists:
      Downloader._TouchTimestampForStaged(directory_path)
    return exists

  def Download(self, archive_url, background=False):
    """Downloads the given build artifacts defined by the |archive_url|.

    If background is set to True, will return back early before all artifacts
    have been downloaded. The artifacts that can be backgrounded are all those
    that are not set as synchronous.

    TODO: refactor this into a common Download method, once unit tests are
    fixed up to make iterating on the code easier.
    """
    # Parse archive_url into rel_path (contains the build target) and
    # short_build.
    # e.g. gs://chromeos-image-archive/{rel_path}/{short_build}
    rel_path, short_build = self.ParseUrl(archive_url)
    # This should never happen. The Devserver should only try to call this
    # method if no previous downloads have been staged for this archive_url.
    assert not Downloader.BuildStaged(archive_url, self._static_dir)
    # Bind build_dir and staging_dir here so we can tell if we need to do any
    # cleanup after an exception occurs before build_dir is set.
    self._lock_tag = self.GenerateLockTag(rel_path, short_build)
    try:
      # Create Dev Server directory for this build and tell other Downloader
      # instances we have processed this build. Note that during normal
      # execution, this lock is only released in the actual downloading
      # procedure called below.
      self._build_dir = devserver_util.AcquireLock(
          static_dir=self._static_dir, tag=self._lock_tag)

      # Replace '/' with '_' in rel_path because it may contain multiple levels
      # which would not be qualified as part of the suffix.
      self._staging_dir = tempfile.mkdtemp(suffix='_'.join(
          [rel_path.replace('/', '_'), short_build]))
      Downloader._TouchTimestampForStaged(self._staging_dir)
      cherrypy.log('Gathering download requirements %s' % archive_url,
                   self._LOG_TAG)
      artifacts = self.GatherArtifactDownloads(
          self._staging_dir, archive_url, self._build_dir, short_build)
      devserver_util.PrepareBuildDirectory(self._build_dir)

      cherrypy.log('Downloading foreground artifacts from %s' % archive_url,
                   self._LOG_TAG)
      background_artifacts = []
      for artifact in artifacts:
        if artifact.Synchronous():
          artifact.Download()
          artifact.Stage()
        else:
          background_artifacts.append(artifact)

      if background:
        self._DownloadArtifactsInBackground(background_artifacts)
      else:
        self._DownloadArtifactsSerially(background_artifacts)

    except Exception, e:
      # Release processing lock, which will remove build components directory
      # so future runs can retry.
      if self._build_dir:
        devserver_util.ReleaseLock(static_dir=self._static_dir,
                                   tag=self._lock_tag, destroy=True)

      self._status_queue.put(e)
      self._Cleanup()
      raise
    return 'Success'

  def _Cleanup(self):
    """Cleans up the staging dir for this downloader instanfce."""
    if self._staging_dir:
      cherrypy.log('Cleaning up staging directory %s' % self._staging_dir,
                   self._LOG_TAG)
      shutil.rmtree(self._staging_dir)

    self._staging_dir = None

  def _DownloadArtifactsSerially(self, artifacts):
    """Simple function to download all the given artifacts serially."""
    cherrypy.log('Downloading artifacts serially.', self._LOG_TAG)
    try:
      for artifact in artifacts:
        artifact.Download()
        artifact.Stage()
    except Exception, e:
      self._status_queue.put(e)

      # Release processing lock, which will remove build components directory
      # so future runs can retry.
      if self._build_dir:
        devserver_util.ReleaseLock(static_dir=self._static_dir,
                                   tag=self._lock_tag, destroy=True)
    else:
      # Release processing lock, keeping directory intact.
      if self._build_dir:
        devserver_util.ReleaseLock(static_dir=self._static_dir,
                                   tag=self._lock_tag)
      self._status_queue.put('Success')
    finally:
      self._Cleanup()

  def _DownloadArtifactsInBackground(self, artifacts):
    """Downloads |artifacts| in the background and signals when complete."""
    cherrypy.log('Invoking background download of artifacts', self._LOG_TAG)
    thread = threading.Thread(target=self._DownloadArtifactsSerially,
                              args=(artifacts,))
    thread.start()

  def GatherArtifactDownloads(self, main_staging_dir, archive_url, build_dir,
                              short_build):
    """Wrapper around devserver_util.GatherArtifactDownloads().

    The wrapper allows mocking and overriding in derived classes.
    """
    return devserver_util.GatherArtifactDownloads(main_staging_dir, archive_url,
                                                  build_dir, short_build)

  def GetStatusOfBackgroundDownloads(self):
    """Returns the status of the background downloads.

    This commands returns the status of the background downloads and blocks
    until a status is returned.
    """
    status = self._status_queue.get()
    # In case anyone else is calling.
    self._status_queue.put(status)
    # If someone is curious about the status of a build, then we should
    # probably keep it around for a bit longer.
    if os.path.exists(self._staging_dir):
      Downloader._TouchTimestampForStaged(self._staging_dir)
    # It's possible we received an exception, if so, re-raise it here.
    if isinstance(status, Exception):
      raise status

    return status


class SymbolDownloader(Downloader):
  """Download and stage debug symbols for a build on the devsever.

  Given a URL to a build on the archive server:

    - Determine if the build already exists.
    - Download and extract the debug symbols to a staging directory.
    - Install symbols to static dir.
  """

  _DONE_FLAG = 'done'
  _LOG_TAG = 'SYMBOL_DOWNLOAD'

  @staticmethod
  def GenerateLockTag(rel_path, short_build):
    return '/'.join([rel_path, short_build, 'symbols'])

  def Download(self, archive_url, _background=False):
    """Downloads debug symbols for the build defined by the |archive_url|.

    The symbols will be downloaded synchronously
    """
    # Parse archive_url into rel_path (contains the build target) and
    # short_build.
    # e.g. gs://chromeos-image-archive/{rel_path}/{short_build}
    rel_path, short_build = self.ParseUrl(archive_url)

    # Bind build_dir and staging_dir here so we can tell if we need to do any
    # cleanup after an exception occurs before build_dir is set.
    self._lock_tag = self.GenerateLockTag(rel_path, short_build)
    if self.SymbolsStaged(archive_url, self._static_dir):
      cherrypy.log(
          'Symbols for build %s have already been staged.' % self._lock_tag,
          self._LOG_TAG)
      return 'Success'

    try:
      # Create Dev Server directory for this build and tell other Downloader
      # instances we have processed this build.
      self._build_dir = devserver_util.AcquireLock(
          static_dir=self._static_dir, tag=self._lock_tag)

      # Replace '/' with '_' in rel_path because it may contain multiple levels
      # which would not be qualified as part of the suffix.
      self._staging_dir = tempfile.mkdtemp(suffix='_'.join(
          [rel_path.replace('/', '_'), short_build]))
      cherrypy.log('Downloading debug symbols from %s' % archive_url,
                   self._LOG_TAG)

      [symbol_artifact] = self.GatherArtifactDownloads(
          self._staging_dir, archive_url, self._static_dir)
      symbol_artifact.Download()
      symbol_artifact.Stage()
      self.MarkSymbolsStaged()

    except Exception:
      # Release processing "lock", which will indicate to future runs that we
      # did not succeed, and so they should try again.
      if self._build_dir:
        devserver_util.ReleaseLock(static_dir=self._static_dir,
                                   tag=self._lock_tag, destroy=True)

      raise
    else:
      # Release processing "lock", keeping directory intact.
      if self._build_dir:
        devserver_util.ReleaseLock(static_dir=self._static_dir,
                                   tag=self._lock_tag)
    finally:
      self._Cleanup()

    return 'Success'

  def GatherArtifactDownloads(self, temp_download_dir, archive_url, static_dir,
                              short_build=None):
    """Call SymbolDownloader-appropriate artifact gathering method.

    @param temp_download_dir: the tempdir into which we're downloading artifacts
                              prior to staging them.
    @param archive_url: the google storage url of the bucket where the debug
                        symbols for the desired build are stored.
    @param staging_dir: the dir into which to stage the symbols
    @param short_build: (ignored)

    @return an iterable of one DebugTarball pointing to the right debug symbols.
            This is an iterable so that it's similar to GatherArtifactDownloads.
            Also, it's possible that someday we might have more than one.
    """
    return devserver_util.GatherSymbolArtifactDownloads(temp_download_dir,
                                                        archive_url,
                                                        static_dir)

  def MarkSymbolsStaged(self):
    """Puts a flag file on disk to signal that symbols are staged."""
    with open(os.path.join(self._build_dir, self._DONE_FLAG), 'w') as flag:
      flag.write(self._DONE_FLAG)

  def SymbolsStaged(self, archive_url, static_dir):
    """Returns True if the build is already staged."""
    rel_path, short_build = self.ParseUrl(archive_url)
    sub_directory = self.GenerateLockTag(rel_path, short_build)
    return os.path.isfile(os.path.join(static_dir,
                                       sub_directory,
                                       self._DONE_FLAG))


class ImagesDownloader(Downloader):
  """Download and stage prebuilt images for a given build.

  Given a URL to a build on the archive server and a list of images:
   - Determine which images have not been staged yet.
   - Download the image archive.
   - Extract missing images to the staging directory.

  """
  _DONE_FLAG = 'staged'
  _LOG_TAG = 'IMAGE_DOWNLOAD'

  # List of images to be staged; empty (default) means all.
  _image_list = []

  # A mapping from test image types to their archived file names.
  _IMAGE_TO_FNAME = {
    'test': 'chromiumos_test_image.bin',
    'base': 'chromiumos_base_image.bin',
    'recovery': 'recovery_image.bin',
  }

  @staticmethod
  def GenerateLockTag(rel_path, short_build):
    return os.path.join('images', rel_path, short_build)

  def Download(self, archive_url, image_list, _background=False):
    """Downloads images in |image_list| from the build defined by |archive_url|.

    Download happens synchronously. |images| may include any of those in
    self._IMAGE_TO_FNAME.keys().

    """
    # Check correctness of image list, remove duplicates.
    if not image_list:
      raise DevServerError('empty list of image types')
    invalid_images = list(set(image_list) - set(self._IMAGE_TO_FNAME.keys()))
    if invalid_images:
      raise DevServerError('invalid images requested: %s' % invalid_images)
    image_list = list(set(image_list))

    # Parse archive_url into rel_path (contains the build target) and
    # short_build.
    # e.g. gs://chromeos-image-archive/{rel_path}/{short_build}
    rel_path, short_build = self.ParseUrl(archive_url)

    # Bind build_dir and staging_dir here so we can tell if we need to do any
    # cleanup after an exception occurs before build_dir is set.
    self._lock_tag = self.GenerateLockTag(rel_path, short_build)
    staged_image_list = self._CheckStagedImages(archive_url, self._static_dir)
    unstaged_image_list = [image for image in image_list
                                 if image not in staged_image_list]
    if not unstaged_image_list:
      cherrypy.log(
          'All requested images (%s) for build %s have already been staged.' %
          (devserver_util.CommaSeparatedList(image_list, is_quoted=True)
           if image_list else 'none',
           self._lock_tag),
          self._LOG_TAG)
      return 'Success'

    cherrypy.log(
        'Image(s) %s for build %s will be staged' %
        (devserver_util.CommaSeparatedList(unstaged_image_list, is_quoted=True),
         self._lock_tag),
        self._LOG_TAG)
    self._image_list = unstaged_image_list

    try:
      # Create a static target directory and lock it for processing. We permit
      # the directory to preexist, as different images might be downloaded and
      # extracted at different times.
      self._build_dir = devserver_util.AcquireLock(
          static_dir=self._static_dir, tag=self._lock_tag,
          create_once=False)

      # Replace '/' with '_' in rel_path because it may contain multiple levels
      # which would not be qualified as part of the suffix.
      self._staging_dir = tempfile.mkdtemp(suffix='_'.join(
          [rel_path.replace('/', '_'), short_build]))
      cherrypy.log('Downloading image archive from %s' % archive_url,
                   self._LOG_TAG)
      dest_static_dir = os.path.join(self._static_dir, self._lock_tag)
      [image_archive_artifact] = self.GatherArtifactDownloads(
          self._staging_dir, archive_url, dest_static_dir)
      image_archive_artifact.Download()
      cherrypy.log('Staging images to %s' % dest_static_dir)
      image_archive_artifact.Stage()
      self._MarkStagedImages(unstaged_image_list)

    except Exception:
      # Release processing "lock", which will indicate to future runs that we
      # did not succeed, and so they should try again.
      if self._build_dir:
        devserver_util.ReleaseLock(static_dir=self._static_dir,
                                   tag=self._lock_tag, destroy=True)
      raise
    else:
      # Release processing "lock", keeping directory intact.
      if self._build_dir:
        devserver_util.ReleaseLock(static_dir=self._static_dir,
                                   tag=self._lock_tag)
    finally:
      self._Cleanup()

    return 'Success'

  def GatherArtifactDownloads(self, temp_download_dir, archive_url, static_dir,
                              short_build=None):
    """Call appropriate artifact gathering method.

    Args:
      temp_download_dir: temporary directory for downloading artifacts to
      archive_url:       URI to the bucket where image archive is stored
      staging_dir:       directory into which to stage extracted images
      short_build:       (ignored)
    Returns:
      list of downloadable artifacts (of type Zipfile), currently containing a
      single object, configured for extracting a predetermined list of images
    """
    return devserver_util.GatherImageArchiveArtifactDownloads(
        temp_download_dir, archive_url, static_dir,
        [self._IMAGE_TO_FNAME[image] for image in self._image_list])

  def _MarkStagedImages(self, image_list):
    """Update the on-disk flag file with the list of newly staged images.

    This does not check for duplicates against already listed images, and will
    add any listed images regardless.

    """
    flag_fname = os.path.join(self._build_dir, self._DONE_FLAG)
    with open(flag_fname, 'a') as flag_file:
      flag_file.writelines([image + '\n' for image in image_list])

  def _CheckStagedImages(self, archive_url, static_dir):
    """Returns a list of images that were already staged.

    Reads the list of images from a flag file, if one is present, and returns
    after removing duplicates.

    """
    rel_path, short_build = self.ParseUrl(archive_url)
    sub_directory = self.GenerateLockTag(rel_path, short_build)
    flag_fname = os.path.join(static_dir, sub_directory, self._DONE_FLAG)
    staged_image_list = []
    # TODO(garnold) make this code immune to race conditions, probably by
    # acquiring a lock around the file access code.
    if os.path.isfile(flag_fname):
      with open(flag_fname) as flag_file:
        staged_image_list = [image.strip() for image in flag_file.readlines()]
    return list(set(staged_image_list))
