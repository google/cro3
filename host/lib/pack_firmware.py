#!/usr/bin/env python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os
import re
import struct
import subprocess
import sys
import tempfile

from tools import Tools
from fdt import Fdt
import tools

# TODO(sjg): Once we have a stable fdt, write some unit tests for this

# TODO(clchiou): Rewrite this part after official flashmap implementation is
# pulled into Chromium OS code base.

# constants imported from lib/fmap.h
FMAP_SIGNATURE = "__FMAP__"
FMAP_VER_MAJOR = 1
FMAP_VER_MINOR = 0
FMAP_STRLEN = 32

FMAP_AREA_STATIC = 1 << 0
FMAP_AREA_COMPRESSED = 1 << 1
FMAP_AREA_RO = 1 << 2

FMAP_HEADER_FORMAT = "<8sBBQI%dsH" % (FMAP_STRLEN)
FMAP_AREA_FORMAT = "<II%dsH" % (FMAP_STRLEN)

FMAP_HEADER_NAMES = (
    'signature',
    'ver_major',
    'ver_minor',
    'base',
    'image_size',
    'name',
    'nareas',
)

FMAP_AREA_NAMES = (
    'offset',
    'size',
    'name',
    'flags',
)

class ConfigError(Exception):
  """A configuration error, normally a mistake in the fdt."""
  pass


class PackError(Exception):
  """A packing error, such as a file being too large for its area."""
  pass


class Entry(dict):
  """The base class for an entry type.

  All entry types are subclasses of this class. It is basically a dictionary
  with a few methods to check that the supplied data is value.

  Subclasses should implement the following methods:

    GetData(): To return the data for this entry as a string.
    RunTools(): To run any required tools to create the data.

  Potentially in the future we could add PutData() to write data from a packed
  image file back into an entry, to allow an image file to be updated.

  Properties which we need in our dictionary:
    offset: Byte offset of area.
    size: Size of area in bytes.
    name: Name of area.
  """
  def __init__(self, props):
    super(Entry, self).__init__(props)
    self._CheckFields(('offset', 'size', 'name'))

  def __getattr__(self, name):
    return self[name]

  def __setattr__(self, name, value):
    self[name] = value

  def _CheckFields(self, fields):
    """Check that listed fields are present.

    Args:
      fields: List of field names to check for.

    Raises:
      ConfigError: if a field is not present.
    """
    for f in fields:
      if f not in self:
        raise ConfigError('Entry %s: missing required field: %s' %
            (self['name'], f))

  def _CheckFieldsInt(self, fields):
    """Check that listed fields are present, and convert them to ints.

    Args:
      fields: List of field names to check for.

    Raises:
      ConfigError: if a field is not present or cannot be converted to an int.
    """
    self._CheckFields(fields)
    for f in fields:
      try:
        self[f] = int(self[f])
      except ValueError as str:
        raise ConfigError("Entry %s, property %s: could not convert '%s'"
            " to integer" % (self['name'], f, self[f]))

  def GetOverlap(self, entry):
    """Returns the amount by which we overlap with the supplied entry.

    Args:
      entry: Entry to check.

    Returns:
      Amount of overlap:
        0: the entries butt up together.
        <0: there is a gap bewteen the entries.
        >0: there is overlap.
    """
    a = [self.offset, self.offset + self.size]
    b = [entry.offset, entry.offset + entry.size]
    return min(a[1], b[1]) - max(a[0], b[0])

  def GetData(self):
    """Method implemented by subclasses to return data for the entry.

    Returns:
      String containing entry data.
    """
    raise PackError('class Entry does not implement GetEntry()')

  def RunTools(self, tools, dir):
    """Method implemented by subclasses to run required tools.

    Some entry types require running external tools to create their data.
    This method provides a convenient way of doing this. The supplied
    temporary directory can be used to store files. These should ideally
    not be deleted by this method, since the user may wish to see them
    later.

    Args:
      tools: Tools object to use to run tools.
      dir: Temporary directory to use to create required files.
    """
    pass


class EntryFmapArea(Entry):
  """A base class for things that actually produce data for the image.

  Properties:
    flags: The FMAP flags, which is an integer made up from the bit values in
        FMAP_AREA_...
  """
  def __init__(self, props):
    super(EntryFmapArea, self).__init__(props)
    self._CheckFields(('flags',))

  def GetData(self):
    """This section is empty"""
    return ''


class EntryFmap(EntryFmapArea):
  """An entry which contains an Fmap section

  Properties:
    base: Base offset of flash device (normally 0).
    size: Size of the flash device (2MB or 4MB typically).
    nareas: Number of areas in the FMAP = number of sections.
    entries: The list of entries to put in the FMAP.
  """

  def __init__(self, props):
    super(EntryFmap, self).__init__(props)
    self._CheckFieldsInt(('ver_major', 'ver_minor'))

  def SetEntries(self, base, image_size, entries):
    self['base'] = base
    self['image_size'] = image_size
    self['nareas'] = len(entries)
    self['entries'] = entries

  def GetData(self):
    def _FormatBlob(format, names, obj):
      params = [obj[name] for name in names]
      return struct.pack(format, *params)

    self._CheckFields(('base', 'size'))
    self['signature'] = FMAP_SIGNATURE
    blob = _FormatBlob(FMAP_HEADER_FORMAT, FMAP_HEADER_NAMES, self)
    for entry in self.entries:
      blob += _FormatBlob(FMAP_AREA_FORMAT, FMAP_AREA_NAMES, entry)

    return blob


class EntryWiped(EntryFmapArea):
  """This entry will be wiped to a particular byte value.

  Properties:
    wipe_value: byte value to set area to.
  """
  def __init__(self, props):
    super(EntryWiped, self).__init__(props)
    self._CheckFields(('wipe_value',))
    if self.wipe_value:
      self.wipe_value = chr(int(self.wipe_value))
    else:
      self.wipe_value = chr(0)
    if len(self.wipe_value) != 1:
        raise ConfigError('wipe_value out of range [00:ff]: %s' %
            repr(self.wipe_value))

  def GetData(self):
    return self.wipe_value * self.size


class EntryBlobString(EntryFmapArea):
  """This entry contains a single string.

  The string is placed in the area.

  Properties:
    self.value: The string value to store.
  """
  def __init__(self, props):
    super(EntryBlobString, self).__init__(props)

  def GetData(self):
    return self.value


class EntryBlob(EntryFmapArea):
  """This entry contains a binary blob.

  Properties:
    self.value: The filename to read to obtain the blob data.
  """
  def __init__(self, props):
    super(EntryBlob, self).__init__(props)

  def GetData(self,):
    filename = self.value
    size = os.stat(filename).st_size
    fd = open(filename, 'rb')
    data = fd.read(size)
    fd.close()
    return data


class EntryKeyBlock(EntryFmapArea):
  """This entry contains a vblock

  Properties:
    keyblock: The filename of the keyblock to use (within the keydir)
        (e.g. 'firmware.keyblock')
    signprivate: Private key filename (e.g. 'firmware_data_key.vbprivk')
    keynelkey: Kernel key filename (e.g. 'kernel_subkey.vbpubk')
    version: Version of vblock (generally 1)
  """
  def __init__(self, props):
    super(EntryKeyBlock, self).__init__(props)
    self._CheckFields(('keyblock', 'signprivate', 'kernelkey'))
    self._CheckFieldsInt(('version','preamble_flags'))

  def RunTools(self, tool, dir):
    """Create a vblock for the given firmware image"""
    self.path = os.path.join(dir, 'vblock.%s' % self.label)
    try:
      prefix = self.keydir + '/'
      args = [
          '--vblock', self.path,
          '--keyblock', prefix + self.keyblock,
          '--signprivate', prefix + self.signprivate,
          '--version', '%d' % self.version,
          '--fv', self.value,
          '--kernelkey', prefix + self.kernelkey,
          '--flags', '%d' % self.preamble_flags,
      ]
      stdout = tool.Run('vbutil_firmware', args)
      if tool.verbose >= 4:
        print stdout

      # Update value to the actual filename to be used
      self.value = self.path
    except tools.CmdError as err:
      raise PackError('Cannot make key block: vbutil_firmware failed\n%s' %
                      err)

  def GetData(self):
    fd = open(self.path, 'rb')
    data = fd.read()
    fd.close()
    return data


class PackFirmware:
  """Class for packing a firmware image

  A firmware image consists of a number of areas, called entries here.
  Together they cover the entire firmware device from start to finish.

  We use the fdt to define the format of the output - things like the
  name, start and size of each entry, as well as what type of thing
  to pack in there.

  We maintain a list of available data files (in self.props) and these can be
  requested by each entry. Each entry is a subclass of Entry, such as
  EntryBlob which handles the 'blob' entry type.

  One of the entry types is the fmap (flash map). It basically has a header
  and a representation of the list of sections. We create this from the fdt
  auotmatically. You can find this format documented here:

      http://code.google.com/p/flashmap/wiki/FmapSpec


  The following methods must be called in order:

    SetupFiles
    SelectFdt
    PackImage
  """
  def __init__(self, output, tools, verbose):
    """
    Args:
      output: A method to call to diplay output:
                def output(msg):
                Args:
                  msg: Message to output.
      tools: A tools object for calling external tools.
      verbose: 0 for silent, 1 for progress only, 2 for some info, 3 for
          full info, 4 for debug info including sub-tool output.
    """
    self.props = {}             # Properties / files we know about.
    self.entries = []           # The entries in the flash image.
    self.output = output
    self.tools = tools
    self.verbose = verbose

  def _GetFlags(self, props):
    """Create the fmap flags value from the given properties.

    Args:
      props: Dictionary containing properties.

    Returns
      Integer containing flags from _FMAP_AREA_...
    """
    flags = FMAP_AREA_STATIC
    if 'read-only' in props:
      flags |= FMAP_AREA_RO
    if 'compressed' in props:
      flags |= FMAP_AREA_COMPRESSED
    return flags

  def _CreateEntry(self, node, props):
    """Create an entry based on a node in the fdt.

    For example this fdt line:

      type = "blob signed";

    means it is a 'blob' type and will create an EntryBlob, and the blob
    used will be self.props['signed'].

    Args:
      node: The node to use with trailing slash, e.g. /flash/ro-stub/
      props: Doctionary containing all properties from the node.

    Returns:
      An entry set up and ready for packing.

    Raises:
      ValueError: If fdt has an unknown entry type.
    """
    entry_list = self.fdt.GetString(node + 'type', 'empty').split()
    ftype = entry_list[0]
    key = None
    if len(entry_list) > 1:
      key = entry_list[1]
      if not self.props.get(key):
        raise ConfigError("%s: Requests property '%s' but we only have %s"
            % (node, key, self.props))

    # Create an entry of the correct type.
    entry = None
    if ftype == 'empty':
      entry = EntryFmapArea(props)
    elif ftype == 'blob':
      entry = EntryBlob(props)
      pass
    elif ftype == 'wiped':
      entry = EntryWiped(props)
      pass
    elif ftype == 'keyblock':
      entry = EntryKeyBlock(props)
      pass
    elif ftype == 'blobstring':
      entry = EntryBlobString(props)
    elif ftype == 'fmap':
      entry = EntryFmap(props)
    else:
      raise ValueError('%s: unknown entry type' % ftype)

    # Store the property if requested
    if entry and key:
      entry['value'] = self.props[key]
    return entry

  def SetupFiles(self, boot, signed, gbb, fwid, keydir):
    """Set up files required for packing the firmware.

    Args:
      boot: Filename of bootloader image.
      signed: Filename of signed bootloader image.
      gbb: Filename of Google Binary Block (GBB).
      fwid: String containing the firmware ID.
      keydir: Key directory to use (containing signing keys).
    """
    self.props['boot'] = boot
    self.props['signed'] = signed
    self.props['gbb'] = gbb
    self.props['fwid'] = fwid
    self.keydir = keydir

  def _CheckOverlap(self):
    """Check that no entries overlap each other.

    We only allow section areas to overlap - anything with actual data in it
    must not overlap.
    """
    entries = sorted(self.entries, key=lambda e: e.offset)
    for e1, e2 in zip(entries, entries[1:]):
      # Allow overlap between "pure" fmap areas, but not any of its subclasses
      # Here we exploit the fact that Entry is a new-style class
      if type(e1) is EntryFmapArea or type(e2) is EntryFmapArea:
        continue

      overlap = e1.GetOverlap(e2)
      if overlap > 0:
        raise ValueError('Flash map entries overlap by %d bytes: '
            '%s: %08x-%08x, %s: %08x-%08x' %
            (overlap, e1.label, e1.offset, e1.offset + e1.size,
             e2.label, e2.offset, e2.offset + e2.size))
      elif overlap is not 0:
        self.output('Warning: Flash map has a gap of %d bytes: '
            '%s: %08x-%08x, %s: %08x-%08x' %
            (-overlap, e1.label, e1.offset, e1.offset + e1.size,
             e2.label, e2.offset, e2.offset + e2.size))

  def SelectFdt(self, fdt):
    """Scan FDT and build entry objects.

    This creates a list of entry objects which we can later use to generate
    a firmware image. Each entry's properties are set up correcty but at this
    stage no data is processed. The result is a list of entries in
    self.entries.

    Args:
      fdt: fdt object containing the device tree.

    Raises:
      ConfigError if an error is detected in the fdt configuration.
    """
    self.fdt = fdt
    root = '/flash/'
    self.image_size = int(fdt.GetIntList(root + 'reg', 2)[1])

    # Scan the flash map in the fdt, creating a list of Entry objects.
    re_label = re.compile('(.*)-(\w*)')
    children = fdt.GetChildren(root)
    for child in children:
      node = root + child
      props = fdt.GetProps(node, True)

      # Read the two cells from the node's /reg property to get entry extent.
      offset, size = fdt.DecodeIntList(node + '/reg', props['reg'], 2)
      props['offset'] = offset
      props['size'] = size

      # The section names must be upper case with underscores, for other tools
      props['name'] = re.sub('-', '_', props['label']).upper()
      props['flags'] = self._GetFlags(props)
      props['keydir'] = self.keydir
      try:
        entry = self._CreateEntry(node + '/', props)
        self.entries.append(entry)

      except ConfigError as err:
        raise ValueError('Config error: %s' % err)

  def PackImage(self, tmpdir, output_path):
    """Pack the various components into a firmware image,

    You must call SetupFiles() and SelectFdt() first, to set things up. Then
    this function will create a firmware image for you.

    Args:
      output_path: Full path of file to contain the resulting image.

    Raises:
      PackError: If unable to fit something in the space available, or a
          required file or setup piece is missing.
    """
    self.tmpdir = tmpdir
    root = '/flash/'

    self._CheckOverlap()

    # Set up a zeroed file of the correct size.
    image = open(output_path, 'wb')
    image.write('\0' * self.image_size)

    # Pack all the entriess.
    for entry in self.entries:
      # Add in the info for the fmap.
      if type(entry) == EntryFmap:
        entry.SetEntries(base=0, image_size=self.image_size,
            entries=self.entries)

      try:
        # First run any required tools.
        entry.RunTools(self.tools, self.tmpdir)
        if 'value' in entry:
          self.output("Pack '%s' into %s" % (entry.value, entry.name))

        # Now read out the data
        data = entry.GetData()
        if self.verbose > 3:            # Debugging
          print 'Entry:', entry.name
          print 'Entry data:', entry
          print 'Data size: %d bytes' % len(data)
        if len(data) > entry.size:
          raise PackError("Data for '%s' too large for area: %d/%#x >"
              " %d/%#x" % (entry.name, len(data), len(data), entry.size,
              entry.size))

        image.seek(entry.offset)
        image.write(data)

      except PackError as err:
        raise ValueError('Packing error: %s' % err)

def _Test():
  """Run any built-in tests."""
  import doctest
  doctest.testmod()

def _PackOutput(msg):
  """Helper function to write output from PackFirmware (verbose level 2).

  This is passed to PackFirmware for it to use to write output.

  Args:
    msg: Message to display.
  """
  print msg

def main():
  """Main function for pack_firmware.

  We provide a way of packing firmware from the command line using this module
  directly.
  """
  parser = optparse.OptionParser()
  parser.add_option('-v', '--verbosity', dest='verbosity', default=1,
      type='int', help='Control verbosity: 0=silent, 1=progress, 3=full, '
      '4=debug')
  parser.add_option('-k', '--key', dest='key', type='string', action='store',
      help='Path to signing key directory (default to dev key)',
      default='##/usr/share/vboot/devkeys')
  parser.add_option('-d', '--dt', dest='fdt', type='string', action='store',
      help='Path to fdt file to use (binary ,dtb)', default='u-boot.dtb')
  parser.add_option('-u', '--uboot', dest='uboot', type='string',
      action='store', help='Executable bootloader file (U-Boot)',
      default='u-boot.bin')
  parser.add_option('-S', '--signed', dest='signed', type='string',
      action='store', help='Path to signed boot binary (U-Boot + BCT + FDT)',
      default='u-boot-fdt-signed.bin')
  parser.add_option('-g', '--gbb', dest='gbb', type='string',
      action='store', help='Path to Google Binary Block file',
      default='gbb.bin')
  parser.add_option('-o', '--outdir', dest='outdir', type='string',
      action='store', help='Path to directory to use for intermediate and '
      'output files', default='out')

  (options, args) = parser.parse_args(sys.argv)

  # Set up the output directory.
  if not os.path.isdir(options.outdir):
    os.makedirs(options.outdir)

  # Get tools and fdt.
  tools = Tools(options.verbosity)
  fdt = Fdt(tools, options.fdt)

  # Pack the firmware.
  pack = PackFirmware(_PackOutput, tools, options.verbosity)
  pack.SetupFiles(boot=options.uboot, signed=options.signed, gbb=options.gbb,
      fwid=tools.GetChromeosVersion(), keydir=options.key)
  pack.SelectFdt(fdt)
  out_fname = os.path.join(options.outdir, 'image.bin')
  pack.PackImage(options.outdir, out_fname)
  print 'Output binary is %s' % out_fname

if __name__ == '__main__':
  if sys.argv[1:2] == ["--test"]:
    _Test(*sys.argv[2:])
  else:
    main()
