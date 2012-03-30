#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cherrypy
import multiprocessing
import os
import shutil
import tempfile

import devserver_util


class Downloader(object):
  """Download images to the devsever.

  Given a URL to a build on the archive server:

    - Determine if the build already exists.
    - Download and extract the build to a staging directory.
    - Package autotest tests.
    - Install components to static dir.
  """

  def __init__(self, static_dir):
    self._static_dir = static_dir
    self._build_dir = None
    self._staging_dir = None
    self._status_queue = multiprocessing.Queue()
    self._lock_tag = None
    self._archive_url = None

  @staticmethod
  def BuildStaged(archive_url, static_dir):
    """Returns True if the build is already staged."""
    target, short_build = archive_url.rsplit('/', 2)[-2:]
    sub_directory = '/'.join([target, short_build])
    return os.path.isdir(os.path.join(static_dir, sub_directory))

  def Download(self, archive_url, background=False):
    """Downloads the given build artifacts defined by the |archive_url|.

    If background is set to True, will return back early before all artifacts
    have been downloaded. The artifacts that can be backgrounded are all those
    that are not set as synchronous.
    """
    # Parse archive_url into target and short_build.
    # e.g. gs://chromeos-image-archive/{target}/{short_build}
    self._archive_url = archive_url.strip('/')
    target, short_build = self._archive_url.rsplit('/', 2)[-2:]

    # Bind build_dir and staging_dir here so we can tell if we need to do any
    # cleanup after an exception occurs before build_dir is set.
    self._lock_tag = '/'.join([target, short_build])
    try:
      # Create Dev Server directory for this build and tell other Downloader
      # instances we have processed this build.
      try:
        self._build_dir = devserver_util.AcquireLock(
            static_dir=self._static_dir, tag=self._lock_tag)
      except devserver_util.DevServerUtilError, e:
        if Downloader.BuildStaged(archive_url, self._static_dir):
          cherrypy.log(
              'Build %s has already been processed.' % self._lock_tag,
              'DOWNLOAD')
          self._status_queue.put('Success')
          return 'Success'
        else:
          raise

      self._staging_dir = tempfile.mkdtemp(suffix='_'.join([target,
                                                            short_build]))
      cherrypy.log('Gathering download requirements %s' % self._archive_url,
                   'DOWNLOAD')
      artifacts = devserver_util.GatherArtifactDownloads(
          self._staging_dir, self._archive_url, short_build, self._build_dir)
      devserver_util.PrepareBuildDirectory(self._build_dir)

      cherrypy.log('Downloading foreground artifacts from %s' % archive_url,
                   'DOWNLOAD')
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

      self._status_queue.put('Success')
    except Exception, e:
      # Release processing lock, which will remove build components directory
      # so future runs can retry.
      if self._build_dir:
        devserver_util.ReleaseLock(static_dir=self._static_dir,
                                   tag=self._lock_tag)

      self._status_queue.put(e)
      self._Cleanup()
      raise

    return 'Success'

  def _Cleanup(self):
    """Cleans up the staging dir for this downloader instanfce."""
    if self._staging_dir:
      cherrypy.log('Cleaning up staging directory %s' % self._staging_dir,
                   'DOWNLOAD')
      shutil.rmtree(self._staging_dir)

    self._staging_dir = None

  def _DownloadArtifactsSerially(self, artifacts):
    """Simple function to download all the given artifacts serially."""
    cherrypy.log('Downloading background artifacts for %s' % self._archive_url,
                 'DOWNLOAD')
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
                                   tag=self._lock_tag)
    else:
      self._status_queue.put('Success')
    finally:
      self._Cleanup()

  def _DownloadArtifactsInBackground(self, artifacts):
    """Downloads |artifacts| in the background and signals when complete."""
    proc = multiprocessing.Process(target=self._DownloadArtifactsSerially,
                                   args=(artifacts,))
    proc.start()

  def GetStatusOfBackgroundDownloads(self):
    """Returns the status of the background downloads.

    This commands returns the status of the background downloads and blocks
    until a status is returned.
    """
    status = self._status_queue.get()
    # In case anyone else is calling.
    self._status_queue.put(status)
    # It's possible we received an exception, if so, re-raise it here.
    if isinstance(status, Exception):
      raise status

    return status
