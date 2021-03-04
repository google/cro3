# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Download a file from CIPD.

This is used for downloading a tool executable managed in CIPD.

CIPD URI format is locally defined for this script.
Example:
cipd://chromiumos/infra/tclint/linux-amd64:${version}
chromiumos/infra/tclint/linux-amd64 is the path sent to cipd tool,
and ${version} is the version defined in CIPD.
"""

import os
import urllib.parse

from chromite.lib import commandline
from chromite.lib import constants
from chromite.lib import cros_build_lib


def GetParser():
  """Creates the argparse parser."""
  parser = commandline.ArgumentParser(description=__doc__)
  parser.add_argument('uri', type='cipd',
                      help='CIPD URI of a file to download.')
  parser.add_argument('output', type='path',
                      help='Location to store the file.')
  return parser


def ParseCipdUri(uri):
  o = urllib.parse.urlparse(uri)
  if o.scheme != 'cipd':
    raise ValueError('wrong scheme: ', o.scheme)
  if ':' not in o.path:
    raise ValueError('version not specified')
  pkgpath, version = o.path.rsplit(':', 1)
  return (o.netloc + pkgpath, version)


def main(argv):
  parser = GetParser()
  options = parser.parse_args(argv)
  options.Freeze()

  (pkgpath, version) = ParseCipdUri(options.uri)
  try:
    cros_build_lib.run(
        [os.path.join(constants.DEPOT_TOOLS_DIR, 'cipd'), 'pkg-fetch',
         '-out', options.output, '-version', version, '-verbose', pkgpath],
        check=True)

  except cros_build_lib.RunCommandError as ex:
    # Hide the stack trace using Die.
    cros_build_lib.Die('%s', ex)
