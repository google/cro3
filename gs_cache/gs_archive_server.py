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
import contextlib
import functools
import os
import StringIO
import subprocess
import sys
import tempfile
import urllib
import urlparse

import cherrypy
import requests

import tarfile_utils
from chromite.lib import cros_logging as logging
from chromite.lib import gs

# some http status codes
_HTTP_OK = 200
_HTTP_PARTIAL_CONTENT = 206
_HTTP_BAD_REQUEST = 400
_HTTP_UNAUTHORIZED = 401
_HTTP_NOT_FOUND = 404
_HTTP_INTERNAL_SERVER_ERROR = 500
_HTTP_SERVICE_UNAVAILABLE = 503

_READ_BUFFER_SIZE_BYTES = 1024 * 1024  # 1 MB
_WRITE_BUFFER_SIZE_BYTES = 1024 * 1024  # 1 MB

# The max size of temporary spool file in memory.
_SPOOL_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB

_logger = logging.getLogger(__file__)


def _log(*args, **kwargs):
  """A wrapper function of logging.debug/info, etc."""
  level = kwargs.pop('level', logging.DEBUG)
  _logger.log(level, extra=cherrypy.request.headers, *args, **kwargs)


def _log_filtered_headers(all_headers, filtered_headers, level=logging.DEBUG):
  """Log the filtered headers only."""
  _log('Filtered headers: %s', {k: all_headers.get(k) for k in
                                filtered_headers}, level=level)


def _check_file_extension(filename, ext_names=None):
  """Check the file name and, optionally, the ext name.

  Args:
    filename: The file name to be checked.
    ext_names: The valid extension of |filename| should have.

  Returns:
    The filename if the check is good.

  Raises:
    ValueError: Raised if the checking failed.
  """
  if not filename:
    raise ValueError('File name is required.')

  for ext_name in ext_names or []:
    if filename.endswith(ext_name):
      break
    else:
      raise ValueError("Extension name of '%s' isn't in %s" % (filename,
                                                               ext_names))
  return filename


def _safe_get_param(all_params, param_name):
  """Check if |param_name| is in |all_params|.

  Args:
    all_params: A dict of all parameters of the call.
    param_name: The parameter name to be checked.

  Returns:
    The value of |param_name|.

  Raises:
    Raise HTTP 400 error when the required parameter isn't in |all_params|.
  """
  try:
    return all_params[param_name]
  except KeyError:
    raise cherrypy.HTTPError(_HTTP_BAD_REQUEST,
                             'Parameter "%s" is required!' % param_name)


def _to_cherrypy_error(func):
  """A decorator to convert Exceptions raised to proper cherrypy.HTTPError."""
  @functools.wraps(func)
  def func_wrapper(*args, **kwargs):
    try:
      return func(*args, **kwargs)
    except requests.HTTPError as err:
      # cherrypy.HTTPError wraps the error messages with HTML tags. But
      # requests.HTTPError also do same work. So return the error message
      # directly.
      cherrypy.response.status = err.response.status_code
      return err.response.content
    except ValueError as err:
      # The exception message is just a plain text, so wrap it with
      # cherrypy.HTTPError to have necessary HTML tags
      raise cherrypy.HTTPError(_HTTP_BAD_REQUEST, err.message)
  return func_wrapper


class _CachingServer(object):
  r"""The interface of caching server for GsArchiveServer.

  This class provides an interface to work with the caching server (usually a
  reversed http proxy server) which caches all intermediate results, e.g.
  downloaded files, etc. and serves to GsArchiveServer.

  The relationship of this class and other components is:
    /-------------(python function call)-----------------------\
    |                                                          |
    v                                                          |
  _CachingServer --(http/socket)--> NGINX --(http/socket)--> GsArchiveServer
                                      ^                        |
                                      |                     (https)
  End user, DUTs ---(http)------------/                        |
                                                               V
                                                         GoogleStorage
  """

  def __init__(self, url):
    """Constructor

    Args:
      url: A tuple of URL scheme and netloc.

    Raises:
      ValueError: Raised when input URL in wrong format.
    """
    self._url = url

  def _call(self, action, path, args=None, headers=None):
    """Helper function to generate all RPC calls to the proxy server."""
    url = urlparse.urlunsplit(self._url + ('%s/%s' % (action, path),
                                           urllib.urlencode(args or {}), None))
    _log('Sending request to caching server: %s', url)
    # The header to control using or bypass cache.
    _log_filtered_headers(headers, ('X-No-Cache',))
    rsp = requests.get(url, headers=headers, stream=True)
    _log('Caching server response %s', rsp.status_code)
    _log_filtered_headers(rsp.headers, ('Content-Type', 'Content-Length',
                                        'X-Cache', 'Cache-Control', 'Date'))
    rsp.raise_for_status()
    return rsp

  def download(self, path, headers=None):
    """Call download RPC."""
    return self._call('download', path, headers=headers)

  def list_member(self, path, headers=None):
    """Call list_member RPC."""
    return self._call('list_member', path, headers=headers)


class GsArchiveServer(object):
  """The backend of Google Storage Cache server."""

  def __init__(self, caching_server):
    self._gsutil = gs.GSContext()
    self._caching_server = caching_server

  @cherrypy.expose
  @_to_cherrypy_error
  def list_member(self, *args):
    """Get file list of an tar archive in CSV format.

    An example, GET /list_member/bucket/path/to/file.tar
    The output is in format of:
      <file name>,<data1>,<data2>,...<data6>
      <file name>,<data1>,<data2>,...<data6>
      ...

    Details:
      <file name>: The file name of the member, in URL percent encoding, e.g.
        path/to/file,name  -> path/to/file%2Cname.
      <data1>: File record start offset, in bytes.
      <data2>: File record size, in bytes.
      <data3>: File record end offset, in bytes.
      <data4>: File content start offset, in bytes.
      <data5>: File content size, in bytes.
      <data6>: File content end offset, in bytes.

    This is an internal RPC and shouldn't be called by end user!

    Args:
      *args: All parts of tar file name (must end with '.tar').

    Returns:
      The generator of CSV stream.
    """
    # TODO(guocb): new parameter to filter the list

    archive = _check_file_extension('/'.join(args), ext_names=['.tar'])
    rsp = self._caching_server.download(archive, cherrypy.request.headers)
    cherrypy.response.headers['Content-Type'] = 'text/csv'

    # We run tar command to get member list of a tar file (python tarfile module
    # is too slow). Option '--block-number/-R' of tar prints out the starting
    # block number for each file record.
    _log('list member of the tar %s', archive)
    tar_tv = tempfile.SpooledTemporaryFile(max_size=_SPOOL_FILE_SIZE_BYTES)
    tar = subprocess.Popen(['tar', 'tv', '--block-number'],
                           stdin=subprocess.PIPE, stdout=tar_tv)
    for chunk in rsp.iter_content(_READ_BUFFER_SIZE_BYTES):
      tar.stdin.write(chunk)

    tar.wait()

    def _tar_member_list():
      with tar_tv, contextlib.closing(StringIO.StringIO()) as stream:
        tar_tv.seek(0)
        for info in tarfile_utils.list_tar_members(tar_tv):
          # Encode file name using URL percent encoding, so ',' in file name
          # becomes to '%2C'.
          stream.write('%s,%d,%d,%d,%d\n' % (
              urllib.quote(info.filename), info.record_start, info.record_size,
              info.content_start, info.size))

          if stream.tell() > _WRITE_BUFFER_SIZE_BYTES:
            yield stream.getvalue()
            stream.seek(0)

        if stream.tell():
          yield stream.getvalue()

      _log('list_member done')

    return _tar_member_list()

  @cherrypy.expose
  @_to_cherrypy_error
  def download(self, *args):
    """Download a file from Google Storage.

    For example: GET /download/bucket/path/to/file. This downloads the file
    gs://bucket/path/to/file.

    Args:
      *args: All parts of the GS file path without gs:// prefix.

    Returns:
      The stream of downloaded file.
    """
    path = 'gs://%s' % _check_file_extension('/'.join(args))

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

  @cherrypy.expose
  @_to_cherrypy_error
  def extract(self, *args, **kwargs):
    """Extract a file from a Tar archive.

    Examples:
      GET /extract/chromeos-image-archive/release/files.tar?file=path/to/file

    Args:
      *args: All parts of the GS path of the archive, without gs:// prefix.
      kwargs: file: The URL ENCODED path of file to be extracted.

    Returns:
      The stream of extracted file.
    """
    # TODO(guocb): support compressed format of tar
    archive = _check_file_extension('/'.join(args), ext_names=['.tar'])
    filename = _safe_get_param(kwargs, 'file')
    _log('Extracting "%s" from "%s".', filename, archive)
    return self._extract_file_from_tar(filename, archive)

  def _extract_file_from_tar(self, filename, archive):
    """Extract file of |filename| from |archive|."""
    # Call `list_member` and search |filename| in it. If found, create another
    # "Range Request" to download that range of bytes.
    all_files = self._caching_server.list_member(
        archive, headers=cherrypy.request.headers)
    # The format of each line is '<filename>,<data1>,<data2>...'. And the
    # filename is encoded by URL percent encoding, so no ',' in filename. Thus
    # search '<filename>,' is good enough for looking up the file information.
    target_str = '%s,' % filename

    for l in all_files.iter_lines(chunk_size=_READ_BUFFER_SIZE_BYTES):
      # TODO(guocb): Seems the searching performance is OK: for a 60K lines
      # list, searching a file in very last takes about 0.1 second. But it
      # would be better if there's a better and not very complex way.

      # We don't split the line by ',' and compare the filename part is because
      # of performance.
      if l.startswith(target_str):
        _log('The line for the file found: %s', l)
        file_info = tarfile_utils.TarMemberInfo._make(l.split(','))
        rsp = self._send_range_request(archive, file_info.content_start,
                                       file_info.size)
        rsp.raise_for_status()
        return rsp.iter_content(_WRITE_BUFFER_SIZE_BYTES)

    raise cherrypy.HTTPError(
        _HTTP_BAD_REQUEST,
        'File "%s" is not in archive "%s"!' % (filename, archive))

  def _send_range_request(self, archive, start, size):
    """Create and send a "Range Request" to caching server.

    Set HTTP Range header and just download the bytes in that "range".
    https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests
    """
    headers = cherrypy.request.headers.copy()
    headers['Range'] = 'bytes=%s-%d' % (start, int(start) + int(size) - 1)
    rsp = self._caching_server.download(archive, headers=headers)

    if rsp.status_code == _HTTP_PARTIAL_CONTENT:
      # Although this is a partial response, it has full content of
      # extracted file. Thus reset the status code and content-length.
      cherrypy.response.status = _HTTP_OK
      cherrypy.response.headers['Content-Length'] = size
    else:
      _log('Expect HTTP_PARTIAL_CONTENT (206), but got %s', rsp.status_code,
           level=logging.ERROR)
      rsp.status_code = _HTTP_INTERNAL_SERVER_ERROR
      rsp.reason = 'Range request failed for "%s"' % archive

    return rsp

  # pylint:disable=protected-access
  download._cp_config = {'response.stream': True}
  list_member._cp_config = {'response.stream': True}
  extract._cp_config = {'response.stream': True}


def _url_type(input_string):
  """Ensure |input_string| is a valid URL and convert to target type.

  The target type is a tuple of (scheme, netloc).
  """
  split_result = urlparse.urlsplit(input_string)
  if not split_result.scheme:
    input_string = 'http://%s' % input_string

  split_result = urlparse.urlsplit(input_string)
  if not split_result.scheme or not split_result.netloc:
    raise argparse.ArgumentTypeError('Wrong URL format: %s' % input_string)

  return split_result.scheme, split_result.netloc


def parse_args(argv):
  """Parse arguments."""
  parser = argparse.ArgumentParser(
      formatter_class=argparse.RawDescriptionHelpFormatter,
      description=__doc__)

  # The service can either bind to a socket or listen to a port, but doesn't do
  # both.
  socket_or_port = parser.add_mutually_exclusive_group(required=True)
  socket_or_port.add_argument('-s', '--socket',
                              help='Unix domain socket to bind')
  socket_or_port.add_argument('-p', '--port', type=int,
                              help='Port number to listen.')

  # TODO(guocb): support Unix domain socket
  parser.add_argument(
      '-c', '--caching-server', required=True, type=_url_type,
      help='URL of the proxy server. Valid format is '
      '[http://]{<hostname>|<IP>}[:<port_number>]. When skipped, the default '
      'scheme is http and port number is 80. Any other components in URL are '
      'ignored.')
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

  cherrypy.server.socket_port = args.port
  cherrypy.server.socket_file = args.socket

  cherrypy.quickstart(GsArchiveServer(_CachingServer(args.caching_server)))


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
