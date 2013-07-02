# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import operator
import os
import time
import re
import shutil
import threading

import artifact_info
import build_artifact
import common_util
import devserver_constants
import downloader
import log_util

# Module-local log function.
def _Log(message, *args):
  return log_util.LogWithTag('XBUDDY', message, *args)

# xBuddy globals
_XBUDDY_CAPACITY = 5
ALIASES = [
  'test',
  'base',
  'recovery',
  'full_payload',
  'stateful',
  'autotest',
]

# TODO(joyc) these should become devserver constants.
# currently, storage locations are embedded in the artifact classes defined in
# build_artifact

PATH_TO = [
  build_artifact.TEST_IMAGE_FILE,
  build_artifact.BASE_IMAGE_FILE,
  build_artifact.RECOVERY_IMAGE_FILE,
  devserver_constants.ROOT_UPDATE_FILE,
  build_artifact.STATEFUL_UPDATE_FILE,
  devserver_constants.AUTOTEST_DIR,
]

ARTIFACTS = [
  artifact_info.TEST_IMAGE,
  artifact_info.BASE_IMAGE,
  artifact_info.RECOVERY_IMAGE,
  artifact_info.FULL_PAYLOAD,
  artifact_info.STATEFUL_PAYLOAD,
  artifact_info.AUTOTEST,
]

IMAGE_TYPE_TO_FILENAME = dict(zip(ALIASES, PATH_TO))
IMAGE_TYPE_TO_ARTIFACT = dict(zip(ALIASES, ARTIFACTS))

# local, official, prefix storage locations
# TODO figure out how to access channels
OFFICIAL_RE = "latest-official.*"
LATEST_RE = "latest.*"
VERSION_PREFIX_RE = "R.*"

LATEST = "latest"

CHANNEL = [
  'stable',
  'beta',
  'dev',
  'canary',
]

# only paired with official
SUFFIX = [
  'release',
  'paladin',
  'factory',
]

class XBuddyException(Exception):
  """Exception classes used by this module."""
  pass


# no __init__ method
#pylint: disable=W0232
class Timestamp():
  """Class to translate build path strings and timestamp filenames."""

  _TIMESTAMP_DELIMITER = 'SLASH'
  XBUDDY_TIMESTAMP_DIR = 'xbuddy_UpdateTimestamps'

  @staticmethod
  def TimestampToBuild(timestamp_filename):
    return timestamp_filename.replace(Timestamp._TIMESTAMP_DELIMITER, '/')

  @staticmethod
  def BuildToTimestamp(build_path):
    return build_path.replace('/', Timestamp._TIMESTAMP_DELIMITER)
#pylint: enable=W0232


class XBuddy():
  """Class that manages image retrieval and caching by the devserver.

  Image retrieval by xBuddy path:
    XBuddy accesses images and artifacts that it stores using an xBuddy
    path of the form: board/version/alias
    The primary xbuddy.Get call retrieves the correct artifact or url to where
    the artifacts can be found.

  Image caching:
    Images and other artifacts are stored identically to how they would have
    been if devserver's stage rpc was called and the xBuddy cache replaces
    build versions on a LRU basis. Timestamps are maintained by last accessed
    times of representative files in the a directory in the static serve
    directory (XBUDDY_TIMESTAMP_DIR).

  Private class members:
    _true_values - used for interpreting boolean values
    _staging_thread_count - track download requests
    _static_dir - where all the artifacts are served from
  """
  _true_values = ['true', 't', 'yes', 'y']

  # Number of threads that are staging images.
  _staging_thread_count = 0
  # Lock used to lock increasing/decreasing count.
  _staging_thread_count_lock = threading.Lock()

  def __init__(self, static_dir):
    self._static_dir = static_dir
    self._timestamp_folder = os.path.join(self._static_dir,
                                          Timestamp.XBUDDY_TIMESTAMP_DIR)

  @classmethod
  def ParseBoolean(cls, boolean_string):
    """Evaluate a string to a boolean value"""
    if boolean_string:
      return boolean_string.lower() in cls._true_values
    else:
      return False

  @staticmethod
  def _TryIndex(alias_chunks, index):
    """Attempt to access an index of an alias. Default None if not found."""
    try:
      return alias_chunks[index]
    except IndexError:
      return None

  def _ResolveVersion(self, board, version):
    """
    Handle version aliases.

    Args:
      board: as specified in the original call. (i.e. x86-generic, parrot)
      version: as entered in the original call. can be
        {TBD, 0. some custom alias as defined in a config file}
        1. latest
        2. latest-{channel}
        3. latest-official-{board suffix}
        4. version prefix (i.e. RX-Y.X, RX-Y, RX)
        5. defaults to latest-local build

    Returns:
      Version number that is compatible with google storage (i.e. RX-X.X.X)

    """
    # TODO (joyc) read from a config file

    version_tuple = version.split('-')

    if re.match(OFFICIAL_RE, version):
      # want most recent official build
      return self._LookupVersion(board,
                                 version_type='official',
                                 suffix=self._TryIndex(version_tuple, 2))

    elif re.match(LATEST_RE, version):
      # want most recent build
      return self._LookupVersion(board,
                                 version_type=self._TryIndex(version_tuple, 1))

    elif re.match(VERSION_PREFIX_RE, version):
      # TODO (joyc) Find complete version if it's only a prefix.
      return version

    else:
      # The given version doesn't match any known patterns.
      # Default to most recent build.
      return self._LookupVersion(board)

  def _InterpretPath(self, path_parts):
    """
    Split and translate the pieces of an xBuddy path name

    input:
      path_parts: the segments of the path xBuddy Get was called with.
      Documentation of path_parts can be found in devserver.py:xbuddy

    Return:
      tuple of (board, version, image_type), as verified exist on gs

    Raises:
      XBuddyException: if the path can't be resolved into valid components
    """
    if len(path_parts) == 3:
      # We have a full path, with b/v/a
      board, version, image_type = path_parts
    elif len(path_parts) == 2:
      # We have only the board and the version, default to test image
      board, version = path_parts
      image_type = ALIASES[0]
    elif len(path_parts) == 1:
      # We have only the board. default to latest test image.
      board = path_parts[0]
      version = LATEST
      image_type = ALIASES[0]
    else:
      # Misshapen beyond recognition
      raise XBuddyException('Invalid path, %s.' % '/'.join(path_parts))

    # Clean up board
    # TODO(joyc) decide what to do with the board suffix

    # Clean up version
    version = self._ResolveVersion(board, version)

    # clean up image_type
    if image_type not in ALIASES:
      raise XBuddyException('Image type %s unknown.' % image_type)

    _Log("board: %s, version: %s, image: %s", board, version, image_type)

    return board, version, image_type

  @staticmethod
  def _LookupVersion(board, version_type=None, suffix=None):
    """Crawl gs for actual version numbers."""
    # TODO (joyc)
    raise NotImplementedError()

  def _ListBuilds(self):
    """ Returns the currently cached builds and their last access timestamp.

    Returns:
      list of tuples that matches xBuddy build/version to timestamps in long
    """
    # update currently cached builds
    build_dict = {}

    filenames = os.listdir(self._timestamp_folder)
    for f in filenames:
      last_accessed = os.path.getmtime(os.path.join(self._timestamp_folder, f))
      build_id = Timestamp.TimestampToBuild(f)
      stale_time = datetime.timedelta(seconds = (time.time()-last_accessed))
      build_dict[build_id] = str(stale_time)
    return_tup = sorted(build_dict.iteritems(), key=operator.itemgetter(1))
    return return_tup

  def _UpdateTimestamp(self, board_id):
    """Update timestamp file of build with build_id."""
    common_util.MkDirP(self._timestamp_folder)
    time_file = os.path.join(self._timestamp_folder,
                             Timestamp.BuildToTimestamp(board_id))
    with file(time_file, 'a'):
      os.utime(time_file, None)

  def _Download(self, gs_url, artifact):
    """Download the single artifact from the given gs_url."""
    with XBuddy._staging_thread_count_lock:
      XBuddy._staging_thread_count += 1
    try:
      downloader.Downloader(self._static_dir, gs_url).Download(
          [artifact])
    finally:
      with XBuddy._staging_thread_count_lock:
        XBuddy._staging_thread_count -= 1

  def _CleanCache(self):
    """Delete all builds besides the first _XBUDDY_CAPACITY builds"""
    cached_builds = [e[0] for e in self._ListBuilds()]
    _Log('In cache now: %s', cached_builds)

    for b in range(_XBUDDY_CAPACITY, len(cached_builds)):
      b_path = cached_builds[b]
      _Log('Clearing %s from cache', b_path)

      time_file = os.path.join(self._timestamp_folder,
                               Timestamp.BuildToTimestamp(b_path))
      os.remove(time_file)
      clear_dir = os.path.join(self._static_dir, b_path)
      try:
        if os.path.exists(clear_dir):
          shutil.rmtree(clear_dir)
      except Exception:
        raise XBuddyException('Failed to clear build in %s.' % clear_dir)


  ############################ BEGIN PUBLIC METHODS

  def List(self):
    """Lists the currently available images & time since last access."""
    return str(self._ListBuilds())

  def Capacity(self):
    """Returns the number of images cached by xBuddy."""
    return str(_XBUDDY_CAPACITY)

  def Get(self, path_parts, return_dir=False):
    """The full xBuddy call, returns resource specified by path_parts.

    Please see devserver.py:xbuddy for full documentation.
    Args:
      path_parts: [board, version, alias] as split from the xbuddy call url
      return_dir: boolean, if set to true, returns the dir name instead.

    Returns:
      Path to the image or update directory on the devserver.
      e.g. http://host/static/x86-generic-release/
      R26-4000.0.0/chromium-test-image.bin
      or
      http://host/static/x86-generic-release/R26-4000.0.0/

    Raises:
      XBuddyException if path is invalid or XBuddy's cache fails
    """
    board, version, image_type = self._InterpretPath(path_parts)
    file_name = IMAGE_TYPE_TO_FILENAME[image_type]

    gs_url = os.path.join(devserver_constants.GOOGLE_STORAGE_IMAGE_DIR,
                          board, version)
    serve_dir = os.path.join(board, version)

    # stage image if not found in cache
    cached = os.path.exists(os.path.join(self._static_dir,
                                         serve_dir,
                                         file_name))
    if not cached:
      artifact = IMAGE_TYPE_TO_ARTIFACT[image_type]
      _Log('Artifact to stage: %s', artifact)

      _Log('Staging %s image from: %s', image_type, gs_url)
      self._Download(gs_url, artifact)
    else:
      _Log('Image already cached.')

    self._UpdateTimestamp('/'.join([board, version]))

    #TODO (joyc): run in sep thread
    self._CleanCache()

    #TODO (joyc) static dir dependent on bug id: 214373
    return_url = os.path.join('static', serve_dir)
    if not return_dir:
      return_url =  os.path.join(return_url, file_name)

    _Log('Returning path to payload: %s', return_url)
    return return_url
