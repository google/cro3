#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cherrypy
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

  def Download(self, archive_url):
    # Parse archive_url into board and build.
    # e.g. gs://chromeos-image-archive/{board}/{build}
    archive_url = archive_url.strip('/')
    board, build = archive_url.rsplit('/', 2)[-2:]

    # Bind build_dir and staging_dir here so we can tell if we need to do any
    # cleanup after an exception occurs before build_dir is set.
    build_dir = staging_dir = None
    lock_tag = '/'.join([board, build])
    try:
      # Create Dev Server directory for this build and tell other Downloader
      # instances we have processed this build.
      try:
        build_dir = devserver_util.AcquireLock(static_dir=self._static_dir,
                                               tag=lock_tag)
      except devserver_util.DevServerUtilError, e:
        cherrypy.log('Refused lock "%s". Assuming build has already been'
                     'processed: %s' % (lock_tag, str(e)), 'DOWNLOAD')
        return 'Success'

      cherrypy.log('Downloading build from %s' % archive_url, 'DOWNLOAD')
      staging_dir = tempfile.mkdtemp(suffix='_'.join([board, build]))
      devserver_util.DownloadBuildFromGS(
          staging_dir=staging_dir, archive_url=archive_url, build=build)

      cherrypy.log('Packaging autotest tests.', 'DOWNLOAD')
      devserver_util.PrepareAutotestPkgs(staging_dir)

      cherrypy.log('Installing build components.', 'DOWNLOAD')
      devserver_util.InstallBuild(
          staging_dir=staging_dir, build_dir=build_dir)
    except Exception:
      # Release processing lock, which will remove build components directory
      # so future runs can retry.
      if build_dir:
        devserver_util.ReleaseLock(static_dir=self._static_dir, tag=lock_tag)
      raise
    finally:
      # Always cleanup after ourselves.
      if staging_dir:
        cherrypy.log('Cleaning up staging directory %s' % staging_dir,
                     'DOWNLOAD')
        shutil.rmtree(staging_dir)

    return 'Success'
