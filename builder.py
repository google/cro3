#!/usr/bin/python

# Copyright (c) 2009-2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Package builder for the dev server."""

import os
import subprocess
import tempfile

from portage import dbapi
from portage import xpak
import cherrypy
import portage

import log_util


# Module-local log function.
def _Log(message, *args):
  return log_util.LogWithTag('BUILD', message, *args)


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
  _Log('Executing: ' + command_name)

  p = subprocess.Popen(command, stdout=subprocess.PIPE)
  output_blob = p.communicate()[0]
  if p.returncode != 0:
    raise subprocess.CalledProcessError(p.returncode, command_name)
  return output_blob


def _FilterInstallMaskFromPackage(in_path, out_path):
  """Filter files matching DEFAULT_INSTALL_MASK out of a tarball.

  Args:
    in_path: Unfiltered tarball.
    out_path: Location to write filtered tarball.
  """

  # Grab metadata about package in xpak format.
  my_xpak = xpak.xpak_mem(xpak.tbz2(in_path).get_data())

  # Build list of files to exclude. The tar command uses a slightly
  # different exclude format than gmerge, so it needs to be adjusted
  # appropriately.
  masks = os.environ['DEFAULT_INSTALL_MASK'].split()
  # Look for complete paths matching the specified pattern.  Leading slashes
  # are removed so that the paths are relative. Trailing slashes are removed
  # so that we delete the directory itself when the '/usr/include/' path is
  # given.
  masks = [mask.strip('/') for mask in masks]
  masks = ['--exclude="./%s"' % mask for mask in masks]
  excludes = '--anchored ' + ' '.join(masks)

  gmerge_dir = os.path.dirname(out_path)
  subprocess.check_call(['mkdir', '-p', gmerge_dir])

  tmpd = tempfile.mkdtemp()
  try:
    # Extract package to temporary directory (excluding masked files).
    cmd = ('pbzip2 -dc --ignore-trailing-garbage=1 %s'
           ' | sudo tar -x -C %s %s --wildcards')
    subprocess.check_call(cmd % (in_path, tmpd, excludes), shell=True)

    # Build filtered version of package.
    cmd = 'sudo tar -c --use-compress-program=pbzip2 -C %s . > %s'
    subprocess.check_call(cmd % (tmpd, out_path), shell=True)
  finally:
    subprocess.check_call(['sudo', 'rm', '-rf', tmpd])

  # Copy package metadata over to new package file.
  xpak.tbz2(out_path).recompose_mem(my_xpak)


def UpdateGmergeBinhost(board, pkg, deep):
  """Add pkg to our gmerge-specific binhost.

  Files matching DEFAULT_INSTALL_MASK are not included in the tarball.
  """

  root = '/build/%s/' % board
  gmerge_pkgdir = os.path.join(root, 'gmerge-packages')
  stripped_link = os.path.join(root, 'stripped-packages')

  # Create gmerge pkgdir and give us permission to write to it.
  subprocess.check_call(['sudo', 'mkdir', '-p', gmerge_pkgdir])
  subprocess.check_call(['sudo', 'ln', '-snf', os.path.basename(gmerge_pkgdir),
                         stripped_link])

  username = os.environ['PORTAGE_USERNAME']
  subprocess.check_call(['sudo', 'chown', username, gmerge_pkgdir])

  # Load databases.
  trees = portage.create_trees(config_root=root, target_root=root)
  vardb = trees[root]['vartree'].dbapi
  bintree = trees[root]['bintree']
  bintree.populate()
  gmerge_tree = dbapi.bintree.binarytree(root, gmerge_pkgdir,
                                         settings=bintree.settings)
  gmerge_tree.populate()

  if deep:
    # If we're in deep mode, fill in the binhost completely.
    gmerge_matches = set(gmerge_tree.dbapi.cpv_all())
    bindb_matches = set(bintree.dbapi.cpv_all())
    installed_matches = set(vardb.cpv_all()) & bindb_matches
  else:
    # Otherwise, just fill in the requested package.
    gmerge_matches = set(gmerge_tree.dbapi.match(pkg))
    bindb_matches = set(bintree.dbapi.match(pkg))
    installed_matches = set(vardb.match(pkg)) & bindb_matches

  # Remove any stale packages that exist in the local binhost but are not
  # installed anymore.
  if bindb_matches - installed_matches:
    subprocess.check_call(['eclean-%s' % board, '-d', 'packages'])

  # Remove any stale packages that exist in the gmerge binhost but are not
  # installed anymore.
  changed = False
  for pkg in gmerge_matches - installed_matches:
    gmerge_path = gmerge_tree.getname(pkg)
    if os.path.exists(gmerge_path):
      os.unlink(gmerge_path)
      changed = True

  # Copy any installed packages that have been rebuilt to the gmerge binhost.
  for pkg in installed_matches:
    build_time, = bintree.dbapi.aux_get(pkg, ['BUILD_TIME'])
    build_path = bintree.getname(pkg)
    gmerge_path = gmerge_tree.getname(pkg)

    # If a package exists in the gmerge binhost with the same build time,
    # don't rebuild it.
    if pkg in gmerge_matches and os.path.exists(gmerge_path):
      old_build_time, = gmerge_tree.dbapi.aux_get(pkg, ['BUILD_TIME'])
      if old_build_time == build_time:
        continue

    _Log('Filtering install mask from %s' % pkg)
    _FilterInstallMaskFromPackage(build_path, gmerge_path)
    changed = True

  # If the gmerge binhost was changed, update the Packages file to match.
  if changed:
    env_copy = os.environ.copy()
    env_copy['PKGDIR'] = gmerge_pkgdir
    env_copy['ROOT'] = root
    env_copy['PORTAGE_CONFIGROOT'] = root
    cmd = ['/usr/lib/portage/bin/emaint', '-f', 'binhost']
    subprocess.check_call(cmd, env=env_copy)

  return bool(installed_matches)


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
    _Log(text)
    return text

  def Build(self, board, pkg, additional_args):
    """Handles a build request from the cherrypy server."""
    _Log('Additional build request arguments: ' + str(additional_args))

    def _AppendStrToEnvVar(env, var, additional_string):
      env[var] = env.get(var, '') + ' ' + additional_string
      _Log('%s flags modified to %s' % (var, env[var]))

    env_copy = os.environ.copy()
    if 'use' in additional_args:
      _AppendStrToEnvVar(env_copy, 'USE', additional_args['use'])

    if 'features' in additional_args:
      _AppendStrToEnvVar(env_copy, 'FEATURES', additional_args['features'])

    try:
      if (self._ShouldBeWorkedOn(board, pkg) and
          not additional_args.get('accept_stable')):
        return self.SetError(
            'Package is not cros_workon\'d on the devserver machine.\n'
            'Either start working on the package or pass --accept_stable '
            'to gmerge')

      # If user did not supply -n, we want to rebuild the package.
      usepkg = additional_args.get('usepkg')
      if not usepkg:
        rc = subprocess.call(['emerge-%s' % board, pkg], env=env_copy)
        if rc != 0:
          return self.SetError('Could not emerge ' + pkg)

      # Sync gmerge binhost.
      deep = additional_args.get('deep')
      if not UpdateGmergeBinhost(board, pkg, deep):
        return self.SetError('Package %s is not installed' % pkg)

      return 'Success\n'
    except OSError, e:
      return self.SetError('Could not execute build command: ' + str(e))
