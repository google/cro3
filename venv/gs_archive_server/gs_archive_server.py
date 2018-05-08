# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The backend service of Google Storage Cache Server.

Run `./bin/gs_archive_server` to start the server. After started, it listens on
a TCP port and/or an Unix domain socket. The latter performs better when work
with a local hosted reverse proxy server, e.g. Nginx.

The server accepts below requests:
  - GET /download/<bucket>/path/to/file: download the file from google storage
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import os
import sys

import cherrypy

from chromite.lib import cros_logging as logging
from chromite.lib import gs

# some http status codes
_HTTP_UNAUTHORIZED = 401
_HTTP_NOT_FOUND = 404
_HTTP_SERVICE_UNAVAILABLE = 503

_logger = logging.getLogger(__file__)


def _log(*args, **kwargs):
  """A wrapper function of logging.debug/info, etc."""
  level = kwargs.pop('level', logging.DEBUG)
  _logger.log(level, extra=cherrypy.request.headers, *args, **kwargs)


class GSArchiveServer(object):
  """The backend of Google Storage Cache server."""

  def __init__(self):
    self._gsutil = gs.GSContext()

  @cherrypy.expose
  def download(self, *args):
    """Download a file from Google Storage.

    For example: GET /download/bucket/path/to/file. This downloads the file
    gs://bucket/path/to/file.

    Args:
      *args: All parts of the GS file path without gs:// prefix.

    Returns:
      The stream of downloaded file.
    """
    path = 'gs://%s' % '/'.join(args)

    _log('Downloading %s', path, level=logging.INFO)
    try:
      stat = self._gsutil.Stat(path)
      content = self._gsutil.StreamingCat(path)
    except gs.GSNoSuchKey as err:
      raise cherrypy.HTTPError(_HTTP_NOT_FOUND, err.message)
    except gs.GSCommandError as err:
      if "You aren't authorized to read" in err.result.error:
        status = _HTTP_UNAUTHORIZED
      else:
        status = _HTTP_SERVICE_UNAVAILABLE
      raise cherrypy.HTTPError(status, '%s: %s' % (err.message,
                                                   err.result.error))

    cherrypy.response.headers.update({
        'Content-Type': stat.content_type,
        'Accept-Ranges': 'bytes',
        'Content-Length': stat.content_length,
    })
    _log('Download complete.')

    return content

  # pylint:disable=protected-access
  download._cp_config = {'response.stream': True}


def parse_args(argv):
  """Parse arguments."""
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('-s', '--socket', help='Unix domain socket to bind')
  parser.add_argument('-p', '--port', type=int, default=8080,
                      help='Port number to listen, default: %(default)s.')
  return parser.parse_args(argv)


def setup_logger():
  """Setup logger."""
  formatter = logging.Formatter(
      '%(module)s:%(asctime)-15s [%(Remote-Addr)s:%(thread)d] %(levelname)s:'
      ' %(message)s')
  handler = logging.StreamHandler(sys.stdout)
  handler.setFormatter(formatter)
  _logger.setLevel(logging.DEBUG)
  _logger.addHandler(handler)


def main(argv):
  """Main function."""
  args = parse_args(argv)
  setup_logger()

  if args.socket:
    # in order to allow group user writing to domain socket, the directory
    # should have GID bit set, i.e. g+s
    os.umask(0002)

    # pylint:disable=protected-access
    domain_server = cherrypy._cpserver.Server()
    domain_server.socket_file = args.socket
    domain_server.subscribe()

  cherrypy.config.update({'server.socket_port': args.port,
                          'server.socket_host': '127.0.0.1'})
  cherrypy.quickstart(GSArchiveServer())


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
