# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script to check if the package(s) have prebuilts.

The script must be run inside the chroot. The output is a json dict mapping the
package atoms to a boolean for whether a prebuilt exists.
"""

from __future__ import print_function

import json
import os

from chromite.lib import commandline
from chromite.lib import cros_build_lib
from chromite.lib import osutils
from chromite.lib import portage_util
from chromite.lib.parser import package_info

if cros_build_lib.IsInsideChroot():
  from chromite.lib import depgraph


def GetParser():
  """Build the argument parser."""
  parser = commandline.ArgumentParser(description=__doc__)

  parser.add_argument(
      '-b',
      '--build-target',
      dest='build_target_name',
      help='The build target that is being checked.')
  parser.add_argument(
      '--output',
      type='path',
      required=True,
      help='The file path where the result json should be stored.')
  parser.add_argument(
      'packages',
      nargs='+',
      help='The package atoms that are being checked.')

  return parser


def _ParseArguments(argv):
  """Parse and validate arguments."""
  parser = GetParser()
  opts = parser.parse_args(argv)

  if not os.path.exists(os.path.dirname(opts.output)):
    parser.error('Path containing the output file does not exist.')

  # Manually parse the packages as CPVs.
  packages = []
  for pkg in opts.packages:
    cpv = package_info.parse(pkg)
    if not cpv.atom:
      parser.error('Invalid package atom: %s' % pkg)

    packages.append(cpv)
  opts.packages = packages

  opts.Freeze()
  return opts


def main(argv):
  opts = _ParseArguments(argv)
  cros_build_lib.AssertInsideChroot()

  board = opts.build_target_name
  bests = {}
  for cpv in opts.packages:
    bests[cpv.atom] = portage_util.PortageqBestVisible(cpv.atom, board=board)

  # Emerge args:
  #   g: use binpkgs (needed to find if we have one)
  #   u: update packages to latest version (want updates to invalidate binpkgs)
  #   D: deep -- consider full tree rather that just immediate deps
  #     (changes in dependencies and transitive deps can invalidate a binpkg)
  #   N: Packages with changed use flags should be considered
  #     (changes in dependencies and transitive deps can invalidate a binpkg)
  #   q: quiet (simplifies output)
  #   p: pretend (don't actually install it)
  args = ['-guDNqp', '--with-bdeps=y', '--color=n']
  if board:
    args.append('--board=%s' % board)
  args.extend('=%s' % best.cpf for best in bests.values())

  generator = depgraph.DepGraphGenerator()
  generator.Initialize(args)

  results = {}
  for atom, best in bests.items():
    results[atom] = generator.HasPrebuilt(best.cpf)

  osutils.WriteFile(opts.output, json.dumps(results))
