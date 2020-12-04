#!/usr/bin/env python3
# Copyright 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility to configure netboot settings."""

import argparse
import socket
import struct
import sys

try:
  import fmap
except ImportError:
  print('Could not find fmap module. If you are running outside the chroot, '
        'ensure that third_party/flashmap is on your PYTHONPATH.',
        file=sys.stderr)
  raise


def _ParseArgs(argv):
  """Construct an ArgumentParser for this utility script."""
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--input', '-i', required=True,
                      help='Path to the firmware to modify; required')
  parser.add_argument('--output', '-o',
                      help='Path to store output; if not specified we will '
                           'directly modify the input file')

  parser.add_argument('--tftpserverip',
                      help='Set the TFTP server IP address (defaults to DHCP-'
                           'provided address)')
  parser.add_argument('--bootfile',
                      help='Set the path of the TFTP boot file (defaults to '
                           'DHCP-provided file name)')
  parser.add_argument('--argsfile',
                      help='Set the path of the TFTP file that provides the '
                           'kernel command line (overrides default and --arg)')

  parser.add_argument('--board',
                      help='Set the cros_board to be passed into the kernel')
  parser.add_argument('--omahaserver',
                      help='Set the Omaha server IP address')
  parser.add_argument('--arg', '--kernel_arg', default=[], dest='kernel_args',
                      metavar='kernel_args', action='append',
                      help='Set extra kernel command line parameters (appended '
                           'to default string for factory)')
  return parser.parse_args(argv)


class Image(object):
  """A class to represent a firmware image.

  Areas in the image should be accessed using the [] operator which takes
  the area name as its key.

  Attributes:
    data: The data in the entire image.
  """

  def __init__(self, data):
    """Initialize an instance of Image

    Args:
      data: The data contianed within the image.
    """
    try:
      # FMAP identifier used by the cros_bundle_firmware family of utilities.
      obj = fmap.fmap_decode(data, fmap_name='FMAP')
    except struct.error:
      # FMAP identifier used by coreboot's FMAP creation tools.
      # The name signals that the FMAP covers the entire flash unlike, for
      # example, the EC RW firmware's FMAP, which might also come as part of
      # the image but covers a smaller section.
      obj = fmap.fmap_decode(data, fmap_name='FLASH')
    self.areas = {}
    for area in obj['areas']:
      self.areas[area['name']] = area
    self.data = data

  def __setitem__(self, key, value):
    """Write data into an area of the image.

    If value is smaller than the area it's being written into, it will be
    padded out with NUL bytes. If it's too big, a ValueError exception
    will be raised.

    Args:
      key: The name of the area to overwrite.
      value: The data to write into the area.

    Raises:
      ValueError: 'value' was too large to write into the selected area.
    """
    area = self.areas[key]
    if len(value) > area['size']:
      raise ValueError('Too much data for FMAP area %s' % key)
    value = value.ljust(area['size'], b'\0')
    self.data = (self.data[:area['offset']] + value +
                 self.data[area['offset'] + area['size']:])

  def __getitem__(self, key):
    """Retrieve the data in an area of the image.

    Args:
      key: The area to retrieve.

    Returns:
      The data in that area of the image.
    """
    area = self.areas[key]
    return self.data[area['offset']:area['offset'] + area['size']]


class Settings(object):
  """A class which represents a collection of settings.

  The settings can be updated after a firmware image has been built.

  Attributes of this class other than the signature constant are stored in
  the 'value' field of each attribute in the attributes dict.

  Attributes:
    signature: A constant which has a signature value at the front of the
        settings when written into the image.
  """
  signature = b'netboot\0'

  class Attribute(object):
    """A class which represents a particular setting.

    Attributes:
      code: An enum value which identifies which setting this is.
      value: The value the setting has been set to.
    """
    def __init__(self, code, value):
      """Initialize an Attribute instance.

      Args:
        code: The code for this attribute.
        value: The initial value of this attribute.
      """
      self.code = code
      self.value = value

    def pack(self):
      """Pack an attribute into a binary representation.

      Returns:
        The binary representation.
      """
      if self.value:
        value = self.value.pack()
      else:
        value = b''
      value_len = len(value)
      pad_len = ((value_len + 3) // 4) * 4 - value_len
      value += b'\0' * pad_len
      format_str = '<II%ds' % (value_len + pad_len)
      return struct.pack(format_str, self.code, value_len, value)

  def __init__(self):
    """Initialize an instance of Settings."""
    attributes = {
        'tftp_server_ip': self.Attribute(1, None),
        'kernel_args': self.Attribute(2, None),
        'bootfile': self.Attribute(3, None),
        'argsfile': self.Attribute(4, None),
    }
    self.__dict__['attributes'] = attributes

  def __setitem__(self, name, value):
    self.attributes[name].value = value

  def __getattr__(self, name):
    return self.attributes[name].value

  def pack(self):
    """Pack a Settings object into a binary representation.

    The packed binary representation can be put into an image.

    Returns:
      A binary representation of the settings.
    """
    value = self.signature
    value += struct.pack('<I', len(self.attributes))
    # This doesn't need to be sorted, but it provides for stable outputs
    # rather than relying on Python dictionary ordering, and is what the
    # code has historically done.
    for _, attr in sorted(self.attributes.items()):
      value += attr.pack()
    return value


class Setting(object):
  """Class for settings that are stored simply as strings."""

  def __init__(self, val):
    """Initialize an instance of Setting.

    Args:
      val: The value of the setting.
    """
    self.val = val

  def pack(self):
    """Pack the setting by returning its value as a string.

    Returns:
      The val field as bytes.
    """
    return self.val.encode()


class IpAddress(Setting):
  """Class for IP address settings."""

  def __init__(self, val):
    """Initialize an IpAddress Setting instance.

    Args:
      val: A string representation of the IP address to be set to.
    """
    in_addr = socket.inet_pton(socket.AF_INET, val)
    super(IpAddress, self).__init__(in_addr)


def main(argv):
  options = _ParseArgs(argv)
  with open(options.input, 'rb') as f:
    image = Image(f.read())

  settings = Settings()
  if options.tftpserverip:
    settings['tftp_server_ip'] = IpAddress(options.tftpserverip)
  kernel_args = ''
  if options.board:
    kernel_args += 'cros_board=' + options.board + ' '
  if options.omahaserver:
    kernel_args += 'omahaserver=' + options.omahaserver + ' '
  kernel_args += ' '.join(options.kernel_args)
  kernel_args += '\0'
  settings['kernel_args'] = Setting(kernel_args)
  if options.bootfile:
    settings['bootfile'] = Setting(options.bootfile + '\0')
  if options.argsfile:
    settings['argsfile'] = Setting(options.argsfile + '\0')

  image['SHARED_DATA'] = settings.pack()

  output_name = options.output or options.input
  with open(output_name, 'wb') as f:
    f.write(image.data)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
