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

import cros_output
from tools import Tools

_base = os.path.dirname(sys.argv[0])

class Fdt:
  """Provides simple access to a flat device tree blob

  Properties:
    fname: Filename of fdt
  """
  def __init__(self, tools, fname):
    self.fname = fname
    self.tools = tools
    _, ext = os.path.splitext(fname)
    self._is_compiled = ext == '.dtb'

  def GetProp(self, node, prop, default=None):
    """Get a property from a device tree.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetProp('/lcd', 'width')
    '1366'

    >>> fdt.GetProp('/', 'fluffy')
    Traceback (most recent call last):
      ...
    CmdError: Command failed: fdtget ../tests/test.dtb / fluffy
    Error at 'fluffy': FDT_ERR_NOTFOUND
    <BLANKLINE>

    This looks up the given node and property, and returns the value as a
    string,

    If the node or property does not exist, this will return the default value.

    Args:
      node: Full path to node to look up.
      prop: Property name to look up.
      default: Default value to return if nothing is present in the fdt, or
          None to raise in this case. This will be converted to a string.

    Returns:
      string containing the property value.

    Raises:
      CmdError: if the property does not exist and no default is provided.
    """
    args = [self.fname, node, prop]
    if default is not None:
      args += ['-d', str(default)]
    out = self.tools.Run('fdtget', args)
    return out.strip()

  def GetProps(self, node, convert_dashes=False):
    """Get all properties from a node.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetProps('/')
    {'compatible': '1853253988 1767976051 1700881007 1634886656 1853253988 \
1767976052 1701278305 842346496', '#size-cells': '1', 'model': \
'NVIDIA Seaboard', '#address-cells': '1', 'interrupt-parent': '1'}

    Args:
      node: node name to look in.
      convert_dashes: True to convert - to _ in node names.

    Returns:
      A dictionary containing all the properties, indexed by node name.
      The entries are simply strings - no decoding of lists or numbers is
      done.

    Raises:
      CmdError: if the node does not exist.
    """
    out = self.tools.Run('fdtget', [self.fname, node, '-p'])
    props = out.strip().splitlines()
    props_dict = {}
    for prop in props:
      name = prop
      if convert_dashes:
        prop = re.sub('-', '_', prop)
      props_dict[prop] = self.GetProp(node, name)
    return props_dict

  def DecodeIntList(self, node, prop, int_list_str, num_values=None):
    """Decode a string into a list of integers.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.DecodeIntList('/', 'galveston', '1 2 3 4')
    [1, 2, 3, 4]

    >>> fdt.DecodeIntList('/', 'galveston', '1 2 3 4', 4)
    [1, 2, 3, 4]

    >>> fdt.DecodeIntList('/', 'galveston', '0xff', 1)
    [255]

    >>> fdt.DecodeIntList('/', 'galveston', '1 2 3 4', 3)
    Traceback (most recent call last):
      ...
    ValueError: GetIntList of node '/' prop 'galveston' returns \
'<type 'list'>', which has 4 elements, but 3 expected

    This decodes a string containing a list of integers like '1 2 3' into
    a list like [1 2 3].

    Args:
      node: Full path to node to report in any error raised.
      prop: Property name to report in any error raised.
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
      raise ValueError, ("GetIntList of node '%s' prop '%s' returns '%s'"
          ", which has %d elements, but %d expected" %
          (node, prop, list, len(int_list), num_values))
    return [int(item, 0) for item in int_list]

  def GetIntList(self, node, prop, num_values=None, default=None):
    """Read a property and decode it into a list of integers.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetIntList('/flash@0/shared-dev-cfg@180000', 'reg')
    [1572864, 262144]

    >>> fdt.GetIntList('/flash/shared-dev-cfg', 'reg')
    [1572864, 262144]

    >>> fdt.GetIntList('/flash/shared-dev-cfg', 'reg', 3)
    Traceback (most recent call last):
      ...
    ValueError: GetIntList of node '/flash/shared-dev-cfg' prop 'reg' returns \
'<type 'list'>', which has 2 elements, but 3 expected

    >>> fdt.GetIntList('/swaffham', 'bulbeck', 2)
    Traceback (most recent call last):
      ...
    CmdError: Command failed: fdtget ../tests/test.dtb /swaffham bulbeck
    Error at '/swaffham': FDT_ERR_NOTFOUND
    <BLANKLINE>
    >>> fdt.GetIntList('/lcd', 'bulbeck', 2, '5 6')
    [5, 6]

    This decodes a property containing a list of integers like '1 2 3' into
    a list like [1 2 3].

    Args:
      node: Full path to node to look up.
      prop: Property name to look up.
      num_values: If not None, then the array is checked to make sure it
          has this many values, and an error is raised if not.

    Returns:
      List of integers.

    Raises:
      ValueError if the list is the wrong size.
      CmdError: if the property does not exist.
    """
    return self.DecodeIntList(node, prop, self.GetProp(node, prop, default),
                              num_values)

  def GetInt(self, node, prop, default=None):
    """Gets an integer from a device tree property.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetInt('/lcd', 'width')
    1366
    >>> fdt.GetInt('/lcd', 'rangiora')
    Traceback (most recent call last):
      ...
    CmdError: Command failed: fdtget ../tests/test.dtb /lcd rangiora
    Error at 'rangiora': FDT_ERR_NOTFOUND
    <BLANKLINE>

    >>> fdt.GetInt('/lcd', 'rangiora', 1366)
    1366

    Args:
      node: Full path to node to look up.
      prop: Property name to look up.

    Raises:
      ValueError if the property cannot be converted to an integer.
      CmdError: if the property does not exist.
    """
    value = self.GetIntList(node, prop, 1, default)[0]
    return int(value)

  def GetString(self, node, prop, default=None):
    """Gets a string from a device tree property.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetString('/display', 'compatible')
    'nvidia,tegra250-display'

    Args:
      node: Full path to node to look up.
      prop: Property name to look up.

    Raises:
      CmdError: if the property does not exist.
    """
    return self.GetProp(node, prop, default)

  def GetFlashNode(self, section, part):
    """Returns the node path to use for a particular flash section/path

    Args:
      section: Section name to look at: ro, rw-a, etc.
      part: Partition name to look at: gbb, vpd, etc.

    Returns:
      Full path to flash node
    """
    return '/flash/%s-%s' % (section, part)

  def GetFlashPart(self, section, part):
    """Returns the setup of the given section/part number in the flash map.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetFlashPart('ro', 'onestop')
    [65536, 524288]

    Args:
      section: Section name to look at: ro, rw-a, etc.
      part: Partition name to look at: gbb, vpd, etc.

    Returns:
      Tuple (position, size) of flash area in bytes.
    """
    return self.GetIntList(self.GetFlashNode(section, part), 'reg', 2)

  def GetFlashPartSize(self, section, part):
    """Returns the size of the given section/part number in the flash map.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetFlashPartSize('ro', 'onestop')
    524288
    >>> fdt.GetFlashPartSize('rw', 'b-onestop')
    32768

    Args:
      section: Section name to look at: ro, rw-a, etc.
      part: Partition name to look at: gbb, vpd, etc.

    Returns:
      Size of flash area in bytes.
    """
    size = self.GetInt(self.GetFlashNode(section, part), 'size', -1)
    if size == -1:
      size = self.GetFlashPart(section, part)[1]
    return size

  def GetChildren(self, node):
    """Returns a list of children of a given node.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
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
    out = self.tools.Run('fdtget', [self.fname, '-l', node])
    return out.strip().splitlines()

  def GetLabel(self, node):
    """Returns the label property of a given node.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetLabel('/flash/ro-onestop')
    'ro-onestop'

    >>> fdt.GetLabel('/go/hotspurs')
    Traceback (most recent call last):
      ...
    CmdError: Command failed: fdtget ../tests/test.dtb /go/hotspurs label
    Error at '/go/hotspurs': FDT_ERR_NOTFOUND
    <BLANKLINE>

    Args:
      node: Node to return label property from.

    Raises:
      CmdError: if the node or property does not exist.
    """
    return self.GetString(node, 'label')

  def Copy(self, new_name):
    """Make a copy of the FDT into another file, and return its object.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
    >>> our_copy = fdt.Copy(os.path.join(_base, '../tests/copy.dtb'))
    >>> our_copy.PutString('/display', 'compatible', 'north')
    >>> fdt.GetString('/display', 'compatible')
    'nvidia,tegra250-display'
    >>> our_copy.GetString('/display', 'compatible')
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

  def PutString(self, node, prop, value_str):
    """Writes a string to a property in the fdt.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
    >>> our_copy = fdt.Copy(os.path.join(_base, '../tests/copy.dtb'))
    >>> our_copy.PutString('/display', 'compatible', 'north')
    >>> fdt.GetString('/display', 'compatible')
    'nvidia,tegra250-display'
    >>> our_copy.PutString('/display', 'compatible', 'south')
    >>> our_copy.GetString('/display', 'compatible')
    'south'

    Args:
      node: Full path to node to look up.
      prop: Property name to look up.
      value_str: String to write.
    """
    args = ['-p', '-t', 's', self.fname, node, prop, value_str]
    self.tools.Run('fdtput', args)

  def PutInteger(self, node, prop, value_int):
    """Writes a string to a property in the fdt.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
    >>> our_copy = fdt.Copy(os.path.join(_base, '../tests/copy.dtb'))
    >>> our_copy.PutString('/display', 'compatible', 'north')
    >>> fdt.GetString('/display', 'compatible')
    'nvidia,tegra250-display'
    >>> our_copy.PutString('/display', 'compatible', 'south')
    >>> our_copy.GetString('/display', 'compatible')
    'south'

    Args:
      node: Full path to node to look up.
      prop: Property name to look up.
      value_int: Integer to write.
    """
    args = ['-p', '-t', 'i', self.fname, node, prop, str(value_int)]
    self.tools.Run('fdtput', args)

  def PutIntList(self, node, prop, int_list):
    """Write a list of integers into an fdt property.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
    >>> fdt.GetIntList('/flash@0/shared-dev-cfg@180000', 'reg')
    [1572864, 262144]

    >>> fdt.PutIntList('/flash/shared-dev-cfg', 'victoria', [1, 2, 3])

    >>> fdt.GetIntList('/flash/shared-dev-cfg', 'victoria', 3)
    [1, 2, 3]

    >>> fdt.PutIntList('/flash/shared-dev-cfg', 'victoria', [3])

    >>> fdt.GetIntList('/flash/shared-dev-cfg', 'victoria', 1)
    [3]

    >>> fdt.PutIntList('/flash/shared-dev-cfg', 'victoria', [])

    >>> fdt.GetIntList('/flash/shared-dev-cfg', 'victoria', 0)
    []

    Args:
      node: Full path to node to look up.
      prop: Property name to look up.
      int_list: List of integers to write.
    """
    value_list = [str(s) for s in int_list]
    args = ['-p', '-t', 'i', self.fname, node, prop]
    args.extend(value_list)
    self.tools.Run('fdtput', args)

  def PutBytes(self, node, prop, bytes_list):
    """Write a sequence of bytes into an fdt property.

    >>> tools = Tools(cros_output.Output())
    >>> fdt = Fdt(tools, os.path.join(_base, '../tests/test.dtb'))
    >>> out_copy = fdt.Copy(os.path.join(_base, '../tests/copy.dtb'))
    >>> out_copy.PutBytes('/', 'foo', (0, 1, 2, 3))
    >>> out_copy.GetProp('/', 'foo')
    '66051'
    >>> out_copy.PutBytes('/', 'foo2', (3, 2, 1, 0, 0, 1, 2, 3))
    >>> out_copy.GetProp('/', 'foo2')
    '50462976 66051'
    >>> out_copy.PutBytes('/', 'foo3', (3, 2, 1))
    >>> out_copy.GetProp('/', 'foo3')
    '3 2 1'

    Args:
      node: Full path to the node to look up.
      prop: Property name to look up.
      bytes_list: List of bytes to write.
    """
    value_list = [str(s) for s in bytes_list]
    args = ['-p', '-t', 'bi', self.fname, node, prop]
    args.extend(value_list)
    self.tools.Run('fdtput', args)

  def Compile(self, arch_dts):
    """Compile an fdt .dts source file into a .dtb binary blob

    >>> tools = Tools(cros_output.Output())
    >>> tools.PrepareOutputDir(None)
    >>> src_path = '../tests/dts'
    >>> src = os.path.join(src_path, 'source.dts')
    >>> fdt = Fdt(tools, src)

    >>> fdt.Compile('')
    >>> os.path.exists(os.path.join(tools.outdir, 'source.dtb'))
    True
    >>> if os.path.exists('../tests/source.dtb'):
    ...   os.remove('../tests/source.dtb')

    # Now check that search paths work
    >>> fdt = Fdt(tools, '../tests/source.dts')
    >>> fdt.Compile('') #doctest:+IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    CmdError: Command failed: dtc -I dts -o /tmp/tmpcYO7Fm/source.dtb -O \
dtb -p 4096 ../tests/source.dts
    DTC: dts->dtb  on file "../tests/source.dts"
    FATAL ERROR: Couldn't open "tegra250.dtsi": No such file or directory
    <BLANKLINE>
    >>> tools.search_paths = ['../tests/dts']
    >>> #fdt.Compile()

    Args:
      arch_dts: Architecture/SOC .dtsi include file.
    """
    if not self._is_compiled:
      root, _ = os.path.splitext(self.fname)

      # Upstream U-Boot requires that we invoke the C preprocessor
      data = self.tools.ReadFile(self.fname)
      fname = self.fname
      search_list = []
      if 'ARCH_CPU_DTS' in data or '#ifdef' in data:
        fname = os.path.join(self.tools.outdir, os.path.basename(root) +
                             '.dts')
        args = ['-E', '-P', '-x', 'assembler-with-cpp', '-D__ASSEMBLY__']
        args += ['-Ulinux']
        args += ['-DARCH_CPU_DTS="%s"' % arch_dts]
        args += ['-DCONFIG_CHROMEOS']
        args += ['-o', fname, self.fname]
        self.tools.Run('cc', args)
        search_list.extend(['-i', os.path.dirname(self.fname)])

      # If we don't have a directory, put it in the tools tempdir
      out_fname = os.path.join(self.tools.outdir, os.path.basename(root) +
                               '.dtb')
      for path in self.tools.search_paths:
        search_list.extend(['-i', path])
      args = ['-I', 'dts', '-o', out_fname, '-O', 'dtb', '-p', '4096']
      args.extend(search_list)
      args.append(fname)
      self.tools.Run('dtc', args)
      self.fname = out_fname
      self._is_compiled = True

def main():
  """Main function for cros_bundle_firmware.

  This just lists out the children of the root node, along with all their
  properties.
  """
  parser = optparse.OptionParser()
  parser.add_option('-d', '--dt', dest='fdt', type='string', action='store',
      help='Path to fdt file to use (binary ,dtb)', default='u-boot.dtb')

  (options, _) = parser.parse_args(sys.argv)
  tools = Tools(cros_output.Output())
  fdt = Fdt(tools, options.fdt)
  children = fdt.GetChildren('/')
  for child in children:
    print '%s: %s\n' % (child, fdt.GetProps('/' + child))


def _Test():
  """Run any built-in tests."""
  import doctest
  assert doctest.testmod().failed == 0

if __name__ == '__main__':
  # If first argument is --test, run testing code.
  if sys.argv[1:2] == ["--test"]:
    _Test()
  else:
    main()
