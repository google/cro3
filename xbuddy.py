# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import operator
import os
import re
import shutil
import time
import threading

import build_util
import artifact_info
import build_artifact
import common_util
import devserver_constants
import downloader
import gsutil_util
import log_util

# Module-local log function.
def _Log(message, *args):
  return log_util.LogWithTag('XBUDDY', message, *args)

_XBUDDY_CAPACITY = 5

# Local build constants
LATEST_LOCAL = "latest-local"
LOCAL_ALIASES = [
  'test',
  'base',
  'dev',
]

LOCAL_FILE_NAMES = [
  devserver_constants.TEST_IMAGE_FILE,

  devserver_constants.BASE_IMAGE_FILE,
  devserver_constants.IMAGE_FILE,
]

LOCAL_ALIAS_TO_FILENAME = dict(zip(LOCAL_ALIASES, LOCAL_FILE_NAMES))

# Google Storage constants
GS_ALIASES = [
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

GS_FILE_NAMES = [
  devserver_constants.TEST_IMAGE_FILE,
  devserver_constants.BASE_IMAGE_FILE,
  devserver_constants.RECOVERY_IMAGE_FILE,
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

GS_ALIAS_TO_FILENAME = dict(zip(GS_ALIASES, GS_FILE_NAMES))
GS_ALIAS_TO_ARTIFACT = dict(zip(GS_ALIASES, ARTIFACTS))

LATEST_OFFICIAL = "latest-official"

LATEST = "latest"
RELEASE = "release"


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

  @staticmethod
  def UpdateTimestamp(timestamp_dir, build_id):
    """Update timestamp file of build with build_id."""
    common_util.MkDirP(timestamp_dir)
    time_file = os.path.join(timestamp_dir,
                             Timestamp.BuildToTimestamp(build_id))
    with file(time_file, 'a'):
      os.utime(time_file, None)
#pylint: enable=W0232


class XBuddy(build_util.BuildObject):
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
    _timestamp_folder - directory with empty files standing in as timestamps
                        for each image currently cached by xBuddy
  """
  _true_values = ['true', 't', 'yes', 'y']

  # Number of threads that are staging images.
  _staging_thread_count = 0
  # Lock used to lock increasing/decreasing count.
  _staging_thread_count_lock = threading.Lock()

  def __init__(self, manage_builds=False,  **kwargs):
    super(XBuddy, self).__init__(**kwargs)
    self._manage_builds = manage_builds
    self._timestamp_folder = os.path.join(self.static_dir,
                                          Timestamp.XBUDDY_TIMESTAMP_DIR)

  @classmethod
  def ParseBoolean(cls, boolean_string):
    """Evaluate a string to a boolean value"""
    if boolean_string:
      return boolean_string.lower() in cls._true_values
    else:
      return False

  def _LookupOfficial(self, board, suffix=RELEASE):
    """Check LATEST-master for the version number of interest."""
    _Log("Checking gs for latest %s-%s image", board, suffix)
    latest_addr = devserver_constants.GS_LATEST_MASTER % {'board':board,
                                                          'suffix':suffix}
    cmd = 'gsutil cat %s' % latest_addr
    msg = 'Failed to find build at %s' % latest_addr
    # Full release + version is in the LATEST file
    version = gsutil_util.GSUtilRun(cmd, msg)

    return devserver_constants.IMAGE_DIR % {'board':board,
                                            'suffix':suffix,
                                            'version':version}

  def _LookupChannel(self, board, channel='stable'):
    """Check the channel folder for the version number of interest."""
    # Get all names in channel dir. Get 10 highest directories by version
    _Log("Checking channel %s for latest %s image", channel, board)
    channel_dir = devserver_constants.GS_CHANNEL_DIR % {'channel':channel,
                                                        'board':board}
    latest_version = gsutil_util.GetLatestVersionFromGSDir(channel_dir)

    # Figure out release number from the version number
    image_url = devserver_constants.IMAGE_DIR % {'board':board,
                                                 'suffix':RELEASE,
                                                 'version':'R*'+latest_version}
    image_dir = os.path.join(devserver_constants.GS_IMAGE_DIR, image_url)

    # There should only be one match on cros-image-archive.
    full_version = gsutil_util.GetLatestVersionFromGSDir(image_dir)

    return devserver_constants.IMAGE_DIR % {'board':board,
                                            'suffix':RELEASE,
                                            'version':full_version}

  def _LookupVersion(self, board, version):
    """Search GS image releases for the highest match to a version prefix."""
    # Build the pattern for GS to match
    _Log("Checking gs for latest %s image with prefix %s", board, version)
    image_url = devserver_constants.IMAGE_DIR % {'board':board,
                                                 'suffix':RELEASE,
                                                 'version':version + '*'}
    image_dir = os.path.join(devserver_constants.GS_IMAGE_DIR, image_url)

    # grab the newest version of the ones matched
    full_version = gsutil_util.GetLatestVersionFromGSDir(image_dir)
    return devserver_constants.IMAGE_DIR % {'board':board,
                                            'suffix':RELEASE,
                                            'version':full_version}

  def _ResolveVersionToUrl(self, board, version):
    """
    Handle version aliases for remote payloads in GS.

    Args:
      board: as specified in the original call. (i.e. x86-generic, parrot)
      version: as entered in the original call. can be
        {TBD, 0. some custom alias as defined in a config file}
        1. latest
        2. latest-{channel}
        3. latest-official-{board suffix}
        4. version prefix (i.e. RX-Y.X, RX-Y, RX)

    Returns:
      image_url is where the image dir is actually found on GS

    """
    # TODO (joychen) Convert separate calls to a dict + error out bad paths

    # Only the last segment of the alias is variable relative to the rest.
    version_tuple = version.rsplit('-', 1)

    if re.match(devserver_constants.VERSION_RE, version):
      # This is supposed to be a complete version number on GS. Return it.
      return devserver_constants.IMAGE_DIR % {'board':board,
                                              'suffix':RELEASE,
                                              'version':version}
    elif version == LATEST_OFFICIAL:
      # latest-official --> LATEST build in board-release
      return self._LookupOfficial(board)
    elif version_tuple[0] == LATEST_OFFICIAL:
      # latest-official-{suffix} --> LATEST build in board-{suffix}
      return self._LookupOfficial(board, version_tuple[1])
    elif version == LATEST:
      # latest --> latest build on stable channel
      return self._LookupChannel(board)
    elif version_tuple[0] == LATEST:
      if re.match(devserver_constants.VERSION_RE, version_tuple[1]):
        # latest-R* --> most recent qualifying build
        return self._LookupVersion(board, version_tuple[1])
      else:
        # latest-{channel} --> latest build within that channel
        return self._LookupChannel(board, version_tuple[1])
    else:
      # The given version doesn't match any known patterns.
      raise XBuddyException("Version %s unknown. Can't find on GS." % version)

  @staticmethod
  def _Symlink(link, target):
    """Symlinks link to target, and removes whatever link was there before."""
    _Log("Linking to %s from %s", link, target)
    if os.path.lexists(link):
      os.unlink(link)
    os.symlink(target, link)

  def _GetLatestLocalVersion(self, board, file_name):
    """Get the version of the latest image built for board by build_image

    Updates the symlink reference within the xBuddy static dir to point to
    the real image dir in the local /build/images directory.

    Args:
      board - board-suffix
      file_name - the filename of the image we have cached

    Returns:
      version - the discovered version of the image.
    """
    latest_local_dir = self.GetLatestImageDir(board)
    if not (latest_local_dir and os.path.exists(latest_local_dir)):
      raise XBuddyException('No builds found for %s. Did you run build_image?' %
                            board)

    # assume that the version number is the name of the directory
    version = os.path.basename(latest_local_dir)

    path_to_image = os.path.join(latest_local_dir, file_name)
    if not os.path.exists(path_to_image):
      raise XBuddyException('%s not found in %s. Did you run build_image?' %
                            (file_name, latest_local_dir))

    # symlink the directories
    common_util.MkDirP(os.path.join(self.static_dir, board))
    link = os.path.join(self.static_dir, board, version)
    XBuddy._Symlink(link, latest_local_dir)

    return version

  def _InterpretPath(self, path_list):
    """
    Split and return the pieces of an xBuddy path name

    input:
      path_list: the segments of the path xBuddy Get was called with.
      Documentation of path_list can be found in devserver.py:xbuddy

    Return:
      tuple of (image_type, board, version)

    Raises:
      XBuddyException: if the path can't be resolved into valid components
    """
    if len(path_list) == 3:
      # We have a full path, with b/v/a
      board, version, image_type = path_list
    elif len(path_list) == 2:
      # We have only the board and the version, default to test image
      board, version = path_list
      image_type = GS_ALIASES[0]
    elif len(path_list) == 1:
      # We have only the board. default to latest test image.
      board = path_list[0]
      version = LATEST
      image_type = GS_ALIASES[0]
    else:
      # Misshapen beyond recognition
      raise XBuddyException('Invalid path, %s.' % '/'.join(path_list))

    return image_type, board, version

  def _SyncRegistryWithBuildImages(self):
    """ Crawl images_dir for build_ids of images generated from build_image.

    This will find images and symlink them in xBuddy's static dir so that
    xBuddy's cache can serve them.
    If xBuddy's _manage_builds option is on, then a timestamp will also be
    generated, and xBuddy will clear them from the directory they are in, as
    necessary.
    """
    build_ids = []
    for b in os.listdir(self.images_dir):
      # Ensure we have directories to track all boards in build/images
      common_util.MkDirP(os.path.join(self.static_dir, b))
      board_dir = os.path.join(self.images_dir, b)
      build_ids.extend(['/'.join([b, v]) for v
                        in os.listdir(board_dir) if not v==LATEST])

    # Check currently registered images
    for f in os.listdir(self._timestamp_folder):
      build_id = Timestamp.TimestampToBuild(f)
      if build_id in build_ids:
        build_ids.remove(build_id)

    # Symlink undiscovered images, and update timestamps if manage_builds is on
    for build_id in build_ids:
      link = os.path.join(self.static_dir, build_id)
      target = os.path.join(self.images_dir, build_id)
      XBuddy._Symlink(link, target)
      if self._manage_builds:
        Timestamp.UpdateTimestamp(self._timestamp_folder, build_id)

  def _ListBuildTimes(self):
    """ Returns the currently cached builds and their last access timestamp.

    Returns:
      list of tuples that matches xBuddy build/version to timestamps in long
    """
    # update currently cached builds
    build_dict = {}

    common_util.MkDirP(self._timestamp_folder)
    filenames = os.listdir(self._timestamp_folder)
    for f in filenames:
      last_accessed = os.path.getmtime(os.path.join(self._timestamp_folder, f))
      build_id = Timestamp.TimestampToBuild(f)
      stale_time = datetime.timedelta(seconds = (time.time()-last_accessed))
      build_dict[build_id] = stale_time
    return_tup = sorted(build_dict.iteritems(), key=operator.itemgetter(1))
    return return_tup

  def _Download(self, gs_url, artifact):
    """Download the single artifact from the given gs_url."""
    with XBuddy._staging_thread_count_lock:
      XBuddy._staging_thread_count += 1
    try:
      _Log('Downloading %s from %s', artifact, gs_url)
      downloader.Downloader(self.static_dir, gs_url).Download(
          [artifact])
    finally:
      with XBuddy._staging_thread_count_lock:
        XBuddy._staging_thread_count -= 1

  def _CleanCache(self):
    """Delete all builds besides the first _XBUDDY_CAPACITY builds"""
    self._SyncRegistryWithBuildImages()
    cached_builds = [e[0] for e in self._ListBuildTimes()]
    _Log('In cache now: %s', cached_builds)

    for b in range(_XBUDDY_CAPACITY, len(cached_builds)):
      b_path = cached_builds[b]
      _Log('Clearing %s from cache', b_path)

      time_file = os.path.join(self._timestamp_folder,
                               Timestamp.BuildToTimestamp(b_path))
      os.unlink(time_file)
      clear_dir = os.path.join(self.static_dir, b_path)
      try:
        # handle symlinks, in the case of links to local builds if enabled
        if self._manage_builds and os.path.islink(clear_dir):
          target = os.readlink(clear_dir)
          _Log('Deleting locally built image at %s', target)

          os.unlink(clear_dir)
          if os.path.exists(target):
            shutil.rmtree(target)
        elif os.path.exists(clear_dir):
          _Log('Deleting downloaded image at %s', clear_dir)
          shutil.rmtree(clear_dir)

      except Exception:
        raise XBuddyException('Failed to clear build in %s.' % clear_dir)

  def _GetFromGS(self, build_id, image_type):
    """Check if the artifact is available locally. Download from GS if not."""
    gs_url = os.path.join(devserver_constants.GS_IMAGE_DIR,
                          build_id)

    # stage image if not found in cache
    file_name = GS_ALIAS_TO_FILENAME[image_type]
    cached = os.path.exists(os.path.join(self.static_dir,
                                         build_id,
                                         file_name))
    if not cached:
      artifact = GS_ALIAS_TO_ARTIFACT[image_type]
      self._Download(gs_url, artifact)
    else:
      _Log('Image already cached.')

  def _GetArtifact(self, path):
    """Interpret an xBuddy path and return directory/file_name to resource."""
    image_type, board, version = self._InterpretPath(path)

    if version in [LATEST_LOCAL, '']:
      # Get a local image
      if image_type not in LOCAL_ALIASES:
        raise XBuddyException('Bad image type: %s. Use one of: %s' %
                              (image_type, LOCAL_ALIASES))

      file_name = LOCAL_ALIAS_TO_FILENAME[image_type]
      version = self._GetLatestLocalVersion(board, file_name)
      image_url = os.path.join(board, version)
    else:
      # Get a remote image
      if image_type not in GS_ALIASES:
        raise XBuddyException('Bad image type: %s. Use one of: %s' %
                              (image_type, GS_ALIASES))
      file_name = GS_ALIAS_TO_FILENAME[image_type]

      # Interpret the version (alias), and get gs address
      image_url = self._ResolveVersionToUrl(board, version)

      self._GetFromGS(image_url, image_type)

    _Log("Get artifact %s from image %s", image_type, image_url)

    return image_url, file_name

  ############################ BEGIN PUBLIC METHODS

  def List(self):
    """Lists the currently available images & time since last access."""
    self._SyncRegistryWithBuildImages()
    builds = self._ListBuildTimes()
    return_string = ''
    for build, timestamp in builds:
      return_string += '<b>' + build + '</b>       '
      return_string += '(time since last access: ' + str(timestamp) + ')<br>'
    return return_string

  def Capacity(self):
    """Returns the number of images cached by xBuddy."""
    return str(_XBUDDY_CAPACITY)

  def Get(self, path_list, return_dir=False):
    """The full xBuddy call, returns resource specified by path_list.

    Please see devserver.py:xbuddy for full documentation.
    Args:
      path_list: [board, version, alias] as split from the xbuddy call url
      return_dir: boolean, if set to true, returns the dir name instead.

    Returns:
      Path to the image or update directory on the devserver.
      e.g. http://host/static/x86-generic/
      R26-4000.0.0/chromium-test-image.bin
      or
      http://host/static/x86-generic/R26-4000.0.0/

    Raises:
      XBuddyException if path is invalid or XBuddy's cache fails
    """
    build_id, file_name = self._GetArtifact(path_list)

    Timestamp.UpdateTimestamp(self._timestamp_folder, build_id)

    #TODO (joyc): run in sep thread
    self._CleanCache()

    #TODO (joyc) static dir dependent on bug id: 214373
    return_url = os.path.join('static', build_id)
    if not return_dir:
      return_url =  os.path.join(return_url, file_name)

    _Log('Returning path to payload: %s', return_url)
    return return_url
