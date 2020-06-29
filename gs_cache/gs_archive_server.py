# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The backend service of Google Storage Cache Server.

Run `./bin/gs_archive_server` to start the server. After started, it listens on
a TCP port and/or an Unix domain socket. The latter performs better when work
with a local hosted reverse proxy server, e.g. Nginx.

The server accepts below requests:
  - GET /download/<bucket>/path/to/file
      Download the file from google storage.
  - GET /extract/<bucket>/path/to/archive?file=path/to/file
      Extract a file form a compressed/uncompressed TAR archive.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import contextlib
import fnmatch
import functools
import httplib
import itertools
import os
import StringIO
import subprocess
import sys
import tempfile
import urllib
import urlparse

import requests
import cherrypy

import constants
import fake_omaha
import tarfile_utils
from chromite.lib import cros_logging as logging
from chromite.lib import gs

_WRITE_BUFFER_SIZE_BYTES = 1024 * 1024  # 1 MB
_MAX_RANGES_PER_REQUEST = 100

# When extract files from TAR (either compressed or uncompressed), we suppose
# the TAR exists, so we can call `download` RPC to get it. It's straightforward
# for uncompressed TAR. But for compressed TAR, we cannot `download` it from
# GS because it doesn't exist there at all. In this case, we call `decompress`
# RPC internally to download and decompress. In order to tell if invoke of
# `download` RPC is a real download, or download+decompress, we use below HTTP
# header as a flag. It can also tell use what's the extension name of the
# compressed tar, e.g. '.tar.gz', etc. We use this information to get the file
# name on GS.
_HTTP_HEADER_COMPRESSED_TAR_EXT = 'X-Compressed-Tar-Ext'

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

  if not ext_names:
    return filename

  for ext_name in ext_names:
    if filename.endswith(ext_name):
      return filename

  raise ValueError("Extension name of '%s' isn't in %s" % (filename,
                                                           ext_names))


def _safe_get_param(all_params, param_name):
  """Check if |param_name| is in |all_params| and has non-empty value.

  Args:
    all_params: A dict of all parameters of the call.
    param_name: The parameter name to be checked.

  Returns:
    A set of all non-empty value.

  Raises:
    Raise HTTP 400 error if no valid parameter in |all_params|.
  """
  try:
    value = all_params[param_name]
  except KeyError:
    raise cherrypy.HTTPError(httplib.BAD_REQUEST,
                             'Parameter "%s" is required!' % param_name)

  return set(value) if isinstance(value, list) else {value}


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
      raise cherrypy.HTTPError(httplib.BAD_REQUEST, err.message)
  return func_wrapper


def _search_lines_by_pattern(all_lines, pattern):
  """Search plain text lines which matches one of shell style glob |patterns|.

  Args:
    all_lines: A list or an iterable object of all plain text lines to be
      searched.
    pattern: A pattern that the target lines matched.

  Returns:
    A set of found lines.
  """
  found_lines = set()
  found_lines |= set(fnmatch.filter(all_lines, pattern))

  return found_lines


def _split_into_chunks(iterable, size):
  """Split the iterable into chunks of |size|.

  Examples:
    >>> list(_split_into_chunks(range(10), 3))
    [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]
    >>> list(_split_into_chunks(xrange(8), 4))
    [[0, 1, 2, 3], [4, 5, 6, 7]]
  """
  iter_ = iter(iterable)
  chunk = list(itertools.islice(iter_, size))
  while chunk:
    yield chunk
    chunk = list(itertools.islice(iter_, size))


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
    _log_filtered_headers(headers, ('Range', 'X-No-Cache',
                                    _HTTP_HEADER_COMPRESSED_TAR_EXT))
    rsp = requests.get(url, headers=headers, stream=True)
    _log('Caching server response %s: %s', rsp.status_code, url)
    _log_filtered_headers(rsp.headers, ('Content-Type', 'Content-Length',
                                        'Content-Range', 'X-Cache',
                                        'Cache-Control', 'Date'))
    rsp.raise_for_status()
    return rsp

  def _download_and_decompress_tar(self, path, ext_name, headers=None):
    """Helper function to download and decompress compressed TAR."""
    # The |path| we have is like foo.tar. Combine with |ext_name| we can get
    # the compressed file name on Google storage, e.g.
    # 'foo.tar' + '.gz' => foo.tar.gz
    # But it's special for '.tgz', i.e. 'foo.tar' + '.tgz' => 'foo.tgz'
    if ext_name == '.tgz':
      path, _ = os.path.splitext(path)

    path = '%s%s' % (path, ext_name)
    _log('Download and decompress %s', path)
    return self._call('decompress', path, headers=headers)

  def download(self, path, headers=None):
    """Download file |path| from the caching server."""
    # When the request comes with header _HTTP_HEADER_COMPRESSED_TAR_EXT, we
    # internally call `decompress` instead of `download` because Google storage
    # only has the compressed version of the file to be "downloaded".
    ext_name = headers.pop(_HTTP_HEADER_COMPRESSED_TAR_EXT, None)

    # RPC `decompress` validates ext_name, so doesn't do that here.
    if ext_name:
      return self._download_and_decompress_tar(path, ext_name, headers=headers)
    else:
      return self._call('download', path, headers=headers)

  def list_member(self, path, headers=None):
    """Call list_member RPC."""
    return self._call('list_member', path, headers=headers)


class GsArchiveServerError(Exception):
  """Standard exception class for GsArchiveServer."""


class GsArchiveServer(object):
  """The backend of Google Storage Cache server."""

  def __init__(self, caching_server):
    self._gsutil = gs.GSContext()
    self._caching_server = caching_server

  @cherrypy.expose
  @_to_cherrypy_error
  def list_dir(self, *args):
    """Lists contents of specified GS bucket/<board>/version."""
    path = 'gs://%s' % _check_file_extension('/'.join(args))
    gs_cmd = ['gsutil', 'ls', path]
    try:
      proc = subprocess.Popen(gs_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      content, error = proc.communicate()
    except subprocess.CalledProcessError as e:
      raise cherrypy.HTTPError(httplib.NOT_FOUND, e.output)
    return content

  @cherrypy.expose
  @cherrypy.config(**{'response.stream': True})
  @_to_cherrypy_error
  def list_member(self, *args):
    """Get file list of an tar archive in CSV format.

    An example, GET /list_member/bucket/path/to/file.tar
    The output is in format of:
      <file name>,<data1>,<data2>,...<data4>
      <file name>,<data1>,<data2>,...<data4>
      ...

    Details:
      <file name>: The file name of the member, in URL percent encoding, e.g.
        path/to/file,name  -> path/to/file%2Cname.
      <data1>: File record start offset, in bytes.
      <data2>: File record size, in bytes.
      <data3>: File content start offset, in bytes.
      <data4>: File content size, in bytes.

    This is an internal RPC and shouldn't be called by end user!

    Args:
      *args: All parts of tar file name (must end with '.tar').

    Returns:
      The generator of CSV stream.
    """
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
    for chunk in rsp.iter_content(constants.READ_BUFFER_SIZE_BYTES):
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
  @cherrypy.config(**{'response.stream': True})
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
    content = None

    try:
      stat = self._gsutil.Stat(path)
      if cherrypy.request.method == 'GET':
        _log('Downloading %s', path, level=logging.INFO)
        content = self._gsutil.StreamingCat(path)
    except gs.GSNoSuchKey as err:
      raise cherrypy.HTTPError(httplib.NOT_FOUND, err.message)
    except gs.GSCommandError as err:
      if "You aren't authorized to read" in err.result.error:
        status = httplib.UNAUTHORIZED
      else:
        status = httplib.SERVICE_UNAVAILABLE
      raise cherrypy.HTTPError(status, '%s: %s' % (err.message,
                                                   err.result.error))

    cherrypy.response.headers.update({
        'Content-Type': stat.content_type,
        'Accept-Ranges': 'bytes',
        'Content-Length': stat.content_length,
    })

    return content

  @cherrypy.expose
  @cherrypy.config(**{'response.stream': True})
  @_to_cherrypy_error
  def extract(self, *args, **kwargs):
    """Extract files from a compressed/uncompressed Tar archive.

    The RPC accepts query 'file=' which is either a file name or a glob pattern.
    The query can be specified multiple times.

    It's optional to encode the file name or pattern in 'percent-encoding', i.e.
    '/' -> '%2F', '*' -> '%2A', etc.

    The RPC accepts two type of queries, i.e. 'file=' and 'pattern=' (accepts
    shell-style wildcards). They can be used mixed and either of them can be
    used multiple times.

    The query can be encoded using 'percent-encoding', i.e. '/' -> '%2F',
    '*' -> '%2A', etc.

    Examples:
      Extracting file 'path/to/file' from files.tgz:
      GET /extract/<bucket>/files.tgz?file=path%2Fto%2Ffile

      Extracting all files in pattern of '*/control' or '*/control.*':
      GET /extract/<bucket>/files.tgz?file=*/control&file=*/control.*

    Args:
      *args: All parts of the GS path of the archive, without gs:// prefix.
      kwargs: file: The path or pattern of file to be extracted.

    Returns:
      The JSON stream of extracted file, in details:
        1. No file match the pattern, return empty json, i.e. '{}'.
        2. One or more files match the pattern, return
          '{filename: content, filename: content, ...}'.
    """
    archive = _check_file_extension(
        '/'.join(args),
        ext_names=['.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tar.xz'])
    files = _safe_get_param(kwargs, 'file')
    if len(files) != 1:
      raise GsArchiveServerError('Cannot extract more than one file at a time.')
    file_to_be_extracted = files.pop()
    _log('Extracting "%s" from "%s".', file_to_be_extracted, archive)
    archive_basename, archive_extname = os.path.splitext(archive)

    headers = cherrypy.request.headers.copy()
    if archive_extname == '.tar':
      decompressed_archive_name = archive
    else:
      # Compressed tar archives: we don't decompress them here. Instead, we
      # suppose they have been decompressed, and continue the routine to extract
      # from the supposed decompressed archive name.
      # The magic is, we set a special HTTP header, and pass it to caching
      # server. Eventually, caching server loops it back to `download` RPC.
      # In `download`, we check this header. If it exists, then call
      # `decompress` RPC other than a normal `download` RPC.
      headers[_HTTP_HEADER_COMPRESSED_TAR_EXT] = archive_extname
      # Get the name of decompressed archive, e.g. foo.tgz => foo.tar,
      # bar.tar.xz => bar.tar, etc.
      if archive_extname == '.tgz':
        decompressed_archive_name = '%s.tar' % archive_basename
      else:
        decompressed_archive_name = archive_basename

    return self._extract_file_from_tar(file_to_be_extracted,
                                       decompressed_archive_name, headers)

  def _extract_file_from_tar(self, target_file, archive, headers=None):
    """Extract file from |archive| with http headers |headers|."""
    # Call `list_member` and search |filename| in it. If found, create another
    # "Range Request" to download that range of bytes.

    all_files = self._caching_server.list_member(archive, headers=headers)

    # Loading the file list into memory doesn't consume too much memory (usually
    # just a few MBs), but which is very helpful for us to search.
    found_lines = _search_lines_by_pattern(
        list(all_files.iter_lines(chunk_size=constants.READ_BUFFER_SIZE_BYTES)),
        '%s,*' % target_file
    )
    if not found_lines:
      _log('No matching files found for %s.', target_file,
           level=logging.WARNING)
      yield None

    # Too many ranges may result in error of 'request header too long'. So we
    # split the files into chunks and request one by one.
    found_files = _split_into_chunks(
        [tarfile_utils.TarMemberInfo._make(urllib.unquote(line).rsplit(
            ',', len(tarfile_utils.TarMemberInfo._fields) - 1))
         for line in found_lines],
        _MAX_RANGES_PER_REQUEST)

    for part_of_found_files in found_files:
      ranges = [(int(f.content_start), int(f.content_start) + int(f.size) - 1)
                for f in part_of_found_files]
      rsp = self._send_range_request(archive, ranges, headers)
      yield rsp.content

  def _send_range_request(self, archive, ranges, headers):
    """Create and send a "Range Request" to caching server.

    Set HTTP Range header and just download the bytes in that "range".
    https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests

    Args:
      archive: The archive file this range request against to.
      ranges: A list of ranges to be downloaded. Each range is a tuple of
        (start, end).
      headers: Http headers of the request.

    Returns:
      An instance of requests.Response if the status code from caching server is
        httplib.PARTIAL_CONTENT.
    """
    ranges = ['%d-%d' % r for r in ranges]
    headers = headers.copy()
    headers['Range'] = 'bytes=%s' % (','.join(ranges))
    rsp = self._caching_server.download(archive, headers=headers)

    if rsp.status_code == httplib.PARTIAL_CONTENT:
      # Although this is a partial response, it has full content of
      # extracted file. Thus reset the status code and content-length.
      cherrypy.response.status = httplib.OK
    else:
      _log('Expect HTTP_PARTIAL_CONTENT (206), but got %s', rsp.status_code,
           level=logging.ERROR)
      rsp.status_code = httplib.INTERNAL_SERVER_ERROR
      rsp.reason = 'Range request failed for "%s"' % archive
    rsp.raise_for_status()
    return rsp

  @cherrypy.expose
  @cherrypy.config(**{'response.stream': True})
  @_to_cherrypy_error
  def decompress(self, *args):
    """Decompress the compressed TAR archive.

    Args:
      *args: All parts of the GS path of the compressed archive, without gs://
          prefix.

    Returns:
      The content generator of decompressed TAR archive.
    """
    zarchive = _check_file_extension(
        '/'.join(args), ext_names=['.tar.gz', '.tar.bz2', '.tar.xz', '.tgz'])
    _log('Decompressing "%s"', zarchive)

    rsp = self._caching_server.download(zarchive,
                                        headers=cherrypy.request.headers)
    cherrypy.response.headers['Content-Type'] = 'application/x-tar'
    cherrypy.response.headers['Accept-Ranges'] = 'bytes'

    basename = os.path.basename(zarchive)
    _, extname = os.path.splitext(basename)

    # Command lines used to decompress file.
    commands = {
        '.gz': ['gzip', '-d', '-c'],
        '.tgz': ['gzip', '-d', '-c'],
        '.xz': ['xz', '-d', '-c'],
        '.bz2': ['bzip2', '-d', '-c'],
    }
    decompressed_file = tempfile.SpooledTemporaryFile(
        max_size=_SPOOL_FILE_SIZE_BYTES)
    proc = subprocess.Popen(commands[extname], stdin=subprocess.PIPE,
                            stdout=decompressed_file)
    _log('Decompress process id: %s.', proc.pid)
    for chunk in rsp.iter_content(constants.READ_BUFFER_SIZE_BYTES):
      proc.stdin.write(chunk)
    proc.stdin.close()
    _log('Decompression done.')
    proc.wait()

    # The header of Content-Length is necessary for supporting range request.
    # So we have to decompress the file locally to get the size. This may cause
    # connection timeout issue if the decompression take too long time (e.g. 90
    # seconds). As a reference, it takes about 10 seconds to decompress a 400MB
    # tgz file.
    decompressed_file.seek(0, os.SEEK_END)
    content_length = decompressed_file.tell()
    _log('Decompressed content length is %d bytes.', content_length)
    cherrypy.response.headers['Content-Length'] = str(content_length)
    decompressed_file.seek(0)

    def decompressed_content():
      _log('Streaming decompressed content of "%s" begin.', zarchive)
      while True:
        data = decompressed_file.read(constants.READ_BUFFER_SIZE_BYTES)
        if not data:
          break
        yield data
      decompressed_file.close()
      _log('Streaming of "%s" done.', zarchive)

    return decompressed_content()


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

  # TODO(crbug.com/1063420) Remove the fake Omaha app once we have the long
  # term solution rolls out.
  cherrypy.tree.mount(fake_omaha.FakeOmaha(), '/update',
                      config=fake_omaha.get_config())

  cherrypy.quickstart(GsArchiveServer(_CachingServer(args.caching_server)))


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
