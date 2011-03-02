#!/usr/bin/python

# Copyright (c) 2009-2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Package builder for the dev server."""
import os
import subprocess
import sys

import cherrypy


def _OutputOf(command):
  """Runs command, a list of arguments beginning with an executable.

  Args:
    command: A list of arguments, beginning with the executable
  Returns:
    The output of the command
  Raises:
    subprocess.CalledProcessError if the command fails
  """
  command_name = ' '.join(command)
  cherrypy.log('Executing: ' + command_name, 'BUILD')

  p = subprocess.Popen(command, stdout=subprocess.PIPE)
  output_blob = p.communicate()[0]
  if p.returncode != 0:
    raise subprocess.CalledProcessError(p.returncode, command_name)
  return output_blob


class Builder(object):
  """Builds packages for the devserver."""

  def _ShouldBeWorkedOn(self, board, pkg):
    """Is pkg a package that could be worked on, but is not?"""
    if pkg in _OutputOf(['cros_workon', '--board=' + board, 'list']):
      return False

    # If it's in the list of possible workon targets, we should be working on it
    return pkg in _OutputOf([
        'cros_workon', '--board=' + board, 'list', '--all'])

  def SetError(self, text):
    cherrypy.response.status = 500
    cherrypy.log(text, 'BUILD')
    return text

  def Build(self, board, pkg, additional_args):
    """Handles a build request from the cherrypy server."""
    cherrypy.log('Additional build request arguments: '+ str(additional_args),
                 'BUILD')

    original_use = os.environ.get('USE', '')
    if 'use' in additional_args:
      os.environ['USE'] = original_use + ' ' + additional_args['use']
      cherrypy.log('USE flags modified to ' + os.environ['USE'], 'BUILD')

    try:
      if (self._ShouldBeWorkedOn(board, pkg) and
          not additional_args.get('accept_stable')):
        return self.SetError(
            'Package is not cros_workon\'d on the devserver machine.\n'
            'Either start working on the package or pass --accept_stable '
            'to gmerge')

      rc = subprocess.call(['emerge-%s' % board, pkg])
      if rc != 0:
        return self.SetError('Could not emerge ' + pkg)

      cherrypy.log('ecleaning %s' % pkg, 'BUILD')
      rc = subprocess.call(['eclean-' + board, '-d', 'packages'])
      if rc != 0:
        return self.SetError('eclean failed')

      cherrypy.log('eclean complete %s' % pkg, 'BUILD')
      return 'Success\n'
    except OSError, e:
      return self.SetError('Could not execute build command: ' + str(e))
    finally:
      os.environ['USE'] =  original_use
