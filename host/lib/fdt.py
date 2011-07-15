#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This library provides basic access to an fdt blob."""

import optparse
import os
import re
import shutil
import sys
import tools
from tools import Tools
from tools import CmdError

_base = os.path.dirname(sys.argv[0])

class Fdt:
  """Provides simple access to a flat device tree blob

  Properties:
    fname: Filename of fdt
  """
  def __init__(self, tools, fname):
    self.fname = fname
    self.tools = tools

  def GetProp(self, key, default=None):
    """Get a property from a device tree.

    >>> fdt = Fdt(Tools(1), os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetProp('/lcd/width')
    '1366'

    >>> fdt.GetProp('/fluffy')
    Traceback (most recent call last):
      ...
    CmdError: Command failed: dtget /home/sjg/trunk/src/platform/dev/host\
/lib/../tests/test.dtb /fluffy
    Error at 'fluffy': FDT_ERR_NOTFOUND
    (Node / exists but you didn't specify a property to print)
    <BLANKLINE>

    This looks up the given key and returns the value as a string, The key
    consists of a node with a property attached, like:

        /path/to/node/property

    If the node or property does not exist, this will return the default value.

    Args:
      key: Key to look up.
      default: Default value to return if nothing is present in the fdt, or
          None to raise in this case. This will be converted to a string.

    Returns:
      string containing the property value.

    Raises:
      CmdError: if the property does not exist and no default is provided.
    """
    args = [self.fname, key]
    if default is not None:
      args += ['-d', str(default)]
    out = self.tools.Run('dtget', args)
    return out.strip()

  def GetProps(self, key, convert_dashes=False):
    """Get all properties from a node.

    >>> fdt = Fdt(Tools(1), os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetProps('/')
    {'compatible': '1853253988 1767976051 1700881007 1634886656 1853253988 \
1767976052 1701278305 842346496', '#size-cells': '1', 'model': \
'NVIDIA Seaboard', '#address-cells': '1', 'interrupt-parent': '1'}

    Args:
      key: node name to look in.
      convert_dashes: True to convert - to _ in node names.

    Returns:
      A dictionary containing all the properties, indexed by node name.
      The entries are simply strings - no decoding of lists or numbers is
      done.

    Raises:
      CmdError: if the node does not exist.
    """
    out = self.tools.Run('dtget', [self.fname, key, '-p'])
    props = out.strip().splitlines()
    props_dict = {}
    for prop in props:
      name = prop
      if convert_dashes:
        prop = re.sub('-', '_', prop)
      props_dict[prop] = self.GetProp(key + '/' + name)
    return props_dict

  def DecodeIntList(self, key, int_list_str, num_values=None):
    """Decode a string into a list of integers.

    >>> fdt = Fdt(Tools(1), os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.DecodeIntList('galveston', '1 2 3 4')
    [1, 2, 3, 4]

    >>> fdt.DecodeIntList('galveston', '1 2 3 4', 4)
    [1, 2, 3, 4]

    >>> fdt.DecodeIntList('galveston', '1 2 3 4', 3)
    Traceback (most recent call last):
      ...
    ValueError: GetIntList of key 'galveston' returns '<type 'list'>', \
which has 4 elements, but 3 expected

    This decodes a string containing a list of integers like '1 2 3' into
    a list like [1 2 3].

    Args:
      key: Key where the value came from (only used for error message).
      int_list_str: String to decode.
      num_values: If not None, then the array is checked to make sure it
          has this many values, and an error is raised if not.

    Returns:
      List of integers.

    Raises:
      ValueError if the list is the wrong size.
    """
    int_list = int_list_str.split()
    if num_values and num_values != len(int_list):
      raise ValueError, ("GetIntList of key '%s' returns '%s', which has "
          "%d elements, but %d expected" % (key, list, len(int_list),
          num_values))
    return [int(item) for item in int_list]

  def GetIntList(self, key, num_values=None):
    """Read a key and decode it into a list of integers.

    >>> fdt = Fdt(Tools(1), os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetIntList('/flash@0/shared-dev-cfg@180000/reg')
    [1572864, 262144]

    >>> fdt.GetIntList('/flash/shared-dev-cfg/reg')
    [1572864, 262144]

    >>> fdt.GetIntList('/flash/shared-dev-cfg/reg', 3)
    Traceback (most recent call last):
      ...
    ValueError: GetIntList of key '/flash/shared-dev-cfg/reg' returns \
'<type 'list'>', which has 2 elements, but 3 expected

    >>> fdt.GetIntList('/swaffham/bulbeck', 2)
    Traceback (most recent call last):
      ...
    CmdError: Command failed: dtget /home/sjg/trunk/src/platform/dev\
/host/lib/../tests/test.dtb /swaffham/bulbeck
    Error at '/swaffham/bulbeck': FDT_ERR_NOTFOUND
    <BLANKLINE>

    This decodes a key containing a list of integers like '1 2 3' into
    a list like [1 2 3].

    Args:
      key: Key to read to get value.
      num_values: If not None, then the array is checked to make sure it
          has this many values, and an error is raised if not.

    Returns:
      List of integers.

    Raises:
      ValueError if the list is the wrong size.
      CmdError: if the property does not exist.
    """
    return self.DecodeIntList(key, self.GetProp(key), num_values)

  def GetInt(self, key):
    """Gets an integer from a device tree property.

    >>> fdt = Fdt(Tools(1), os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetInt('/lcd/width')
    1366

    Args:
      key: Key to read to get value.

    Raises:
      ValueError if the property cannot be converted to an integer.
      CmdError: if the property does not exist.
    """
    value = self.GetIntList(key, 1)[0]
    return int(value)

  def GetString(self, key, default=None):
    """Gets a string from a device tree property.

    >>> fdt = Fdt(Tools(1), os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetString('/display/compatible')
    'nvidia,tegra250-display'

    Args:
      key: Key to read to get value.

    Raises:
      CmdError: if the property does not exist.
    """
    return self.GetProp(key, default)

  def GetFlashPart(self, section, part):
    """Returns the setup of the given section/part number in the flash map.

    >>> fdt = Fdt(Tools(1), os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetFlashPart('ro', 'onestop')
    [65536, 524288]

    Args:
      section: Section name to look at: ro, rw-a, etc.
      part: Partition name to look at: gbb, vpd, etc.

    Returns:
      Tuple (position, size) of flash area in bytes.
    """
    return self.GetIntList('/flash/%s-%s/reg' % (section, part), 2)

  def GetFlashPartSize(self, section, part):
    """Returns the size of the given section/part number in the flash map.

    >>> fdt = Fdt(Tools(1), os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetFlashPartSize('ro', 'onestop')
    524288

    Args:
      section: Section name to look at: ro, rw-a, etc.
      part: Partition name to look at: gbb, vpd, etc.

    Returns:
      Size of flash area in bytes.
    """
    return self.GetFlashPart(section, part)[1]

  def GetChildren(self, key):
    """Returns a list of children of a given node.

    >>> fdt = Fdt(Tools(1), os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetChildren('/amba')
    ['interrupt-controller@50041000']

    >>> fdt.GetChildren('/flash@0')
    ['onestop-layout@0', 'firmware-image@0', 'verification-block@7df00', \
'firmware-id@7ff00', 'readonly@0', 'bct@0', 'ro-onestop@10000', \
'ro-gbb@90000', 'ro-data@b0000', 'ro-vpd@c0000', 'fmap@d0000', \
'readwrite@100000', 'rw-vpd@100000', 'shared-dev-cfg@180000', \
'shared-data@1c0000', 'shared-env@1ff000', 'readwrite-a@200000', \
'rw-a-onestop@200000', 'readwrite-b@300000', 'rw-b-onestop@300000']

    Args:
      node: Node to return children from.

    Returns:
      List of children in the node.

    Raises:
      CmdError: if the node does not exist.
    """
    out = self.tools.Run('dtget', [self.fname, '-l', key])
    return out.strip().splitlines()

  def GetLabel(self, key):
    """Returns the label property of a given node.

    >>> fdt = Fdt(Tools(1), os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetLabel('/flash/ro-onestop')
    'ro-onestop'

    >>> fdt.GetLabel('/go/hotspurs')
    Traceback (most recent call last):
      ...
    CmdError: Command failed: dtget /home/sjg/trunk/src/platform/dev/host\
/lib/../tests/test.dtb /go/hotspurs/label
    Error at '/go/hotspurs/label': FDT_ERR_NOTFOUND
    <BLANKLINE>

    Args:
      key: Node to return label property from.

    Raises:
      CmdError: if the node or property does not exist.
    """
    return self.GetString(key + '/label')

  def Copy(self, new_name):
    """Make a copy of the FDT into another file, and return its object.

    >>> fdt = Fdt(Tools(1), os.path.join(_base, '../tests/test.dtb'))
    >>> our_copy = fdt.Copy(os.path.join(_base, '../tests/copy.dtb'))
    >>> our_copy.PutString('/display/compatible', 'north')
    >>> fdt.GetString('/display/compatible')
    'nvidia,tegra250-display'
    >>> our_copy.GetString('/display/compatible')
    'north'

    This copies the FDT into a supplied file, then creates an FDT object to
    access the copy.

    Args:
      new_name: Filename to write copy to.

    Returns:
      An Fdt object for the copy.
    """
    shutil.copyfile(self.tools.Filename(self.fname),
        self.tools.Filename(new_name))
    return Fdt(self.tools, new_name)

  def PutString(self, key, value_str):
    """Writes a string to a property in the fdt.

    >>> fdt = Fdt(Tools(1), os.path.join(_base, '../tests/test.dtb'))
    >>> our_copy = fdt.Copy(os.path.join(_base, '../tests/copy.dtb'))
    >>> our_copy.PutString('/display/compatible', 'north')
    >>> fdt.GetString('/display/compatible')
    'nvidia,tegra250-display'
    >>> our_copy.PutString('/display/compatible', 'south')
    >>> our_copy.GetString('/display/compatible')
    'south'

    Args:
      key: Key to write value to.
      value_str: String to write.
    """
    args = ['-t', 's', self.fname, key, value_str]
    self.tools.Run('dtput', args)

  def PutInteger(self, key, value_int):
    """Writes a string to a property in the fdt.

    >>> fdt = Fdt(Tools(1), os.path.join(_base, '../tests/test.dtb'))
    >>> our_copy = fdt.Copy(os.path.join(_base, '../tests/copy.dtb'))
    >>> our_copy.PutString('/display/compatible', 'north')
    >>> fdt.GetString('/display/compatible')
    'nvidia,tegra250-display'
    >>> our_copy.PutString('/display/compatible', 'south')
    >>> our_copy.GetString('/display/compatible')
    'south'

    Args:
      key: Key to write value to.
      value_int: Integer to write.
    """
    args = ['-t', 'i', self.fname, key, str(value_int)]
    self.tools.Run('dtput', args)


def main():
  """Main function for cros_bundle_firmware.

  This just lists out the children of the root node, along with all their
  properties.
  """
  parser = optparse.OptionParser()
  parser.add_option('-d', '--dt', dest='fdt', type='string', action='store',
      help='Path to fdt file to use (binary ,dtb)', default='u-boot.dtb')

  (options, args) = parser.parse_args(sys.argv)
  tools = Tools(1)
  fdt = Fdt(tools, options.fdt)
  children = fdt.GetChildren('/')
  for child in children:
    print '%s: %s\n' % (child, fdt.GetProps('/' + child))


def _Test(argv):
  """Run any built-in tests."""
  import doctest
  doctest.testmod()

if __name__ == '__main__':
  # If first argument is --test, run testing code.
  if sys.argv[1:2] == ["--test"]:
    _Test([sys.argv[0]] + sys.argv[2:])
  else:
    main()
