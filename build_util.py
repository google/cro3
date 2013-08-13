# Copyright (c) 2009-2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys


class BuildObject(object):
  """
  Common base class that defines key paths in the source tree.

  Classes that inherit from BuildObject can access scripts in the src/scripts
  directory, and have a handle to the static directory of the devserver.
  """
  def __init__(self, root_dir, static_dir):
    self.devserver_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    self.static_dir = static_dir
    try:
      chroot_dir = os.environ['CROS_WORKON_SRCROOT']
      self.scripts_dir = os.path.join(chroot_dir, 'src/scripts')
      self.images_dir = os.path.join(chroot_dir, 'src/build/images')
    except KeyError:
      # Outside of chroot: This is a corner case. Since we live either in
      # platform/dev or /usr/bin/, scripts have to live in ../../../src/scripts
      self.scripts_dir = os.path.abspath(os.path.join(
          self.devserver_dir, '../../../src/scripts'))
      self.images_dir = os.path.abspath(os.path.join(
          self.devserver_dir, '../../../src/build/images'))

  def GetLatestImageDir(self, board):
    """Returns the latest image dir based on shell script."""
    cmd = '%s/get_latest_image.sh --board %s' % (self.scripts_dir, board)
    return os.popen(cmd).read().strip()

  def GetDefaultBoardID(self):
    """Returns the default board id stored in .default_board.

    Default to x86-generic, if that isn't set.
    """
    board_file = '%s/.default_board' % (self.scripts_dir)
    try:
      with open(board_file) as bf:
        return bf.read().strip()
    except IOError:
      return 'x86-generic'
