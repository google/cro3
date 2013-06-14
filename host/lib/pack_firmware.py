#!/usr/bin/env python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import binascii
import hashlib
import optparse
import os
import re
import shutil
import struct
import sys

from tools import CmdError
from tools import Tools
from fdt import Fdt

# Attributes defined outside __init__
#pylint: disable=W0201

# TODO(sjg): Once we have a stable fdt, write some unit tests for this

# TODO(clchiou): Rewrite this part after official flashmap implementation is
# pulled into Chromium OS code base.

# Use this to find the FDT containing the flashmap
FDTMAP_SIGNATURE = '__FDTM__'

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
    pack: The PackFirmware object (essentially this is our parent)
    offset: Byte offset of area.
    size: Size of area in bytes.
    name: Name of area.
    required: True if this entry is required in the image, False if not

  Properties which we create:
    value: The value that we obtain for this entry. This is a list of
        filenames.
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
      except ValueError:
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

  def RunTools(self, tools, out, tmpdir):
    """Method implemented by subclasses to run required tools.

    Some entry types require running external tools to create their data.
    This method provides a convenient way of doing this. The supplied
    temporary directory can be used to store files. These should ideally
    not be deleted by this method, since the user may wish to see them
    later.

    Args:
      tools: Tools object to use to run tools.
      out: Output object to send output to
      tmpdir: Temporary directory to use to create required files.
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
    def _FormatBlob(fmt, names, obj):
      params = [obj[name] for name in names]
      return struct.pack(fmt, *params)

    self._CheckFields(('base', 'size'))
    self['signature'] = FMAP_SIGNATURE
    blob = _FormatBlob(FMAP_HEADER_FORMAT, FMAP_HEADER_NAMES, self)
    for entry in self.entries:
      blob += _FormatBlob(FMAP_AREA_FORMAT, FMAP_AREA_NAMES, entry)

    return blob


class EntryFdtMap(EntryFmapArea):
  """An entry which contains an FDT-based flashmap

  Properties:
    base: Base offset of flash device (normally 0).
    size: Size of the flash device (2MB or 4MB typically).
  """

  def __init__(self, props):
    super(EntryFdtMap, self).__init__(props)

  # We could potentially include only the flashmap node, but for now put
  # the entire FDT in this region. It provides easy access to all
  # configuration.
  def GetData(self):
    data = self.pack.tools.ReadFile(self.pack.props['fdtmap'])
    crc32 = binascii.crc32(data) & 0xffffffff
    blob = struct.pack('<8sLL', FDTMAP_SIGNATURE, len(data), crc32)
    blob += data

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
    return self.value[0]


class EntryIfd(EntryFmapArea):
  """This entry marks the use of an Intel Firmware Descriptor.

  The entry itself covers the 'Intel' part of the firmware, containing the
  firmware descriptor and management engine. When this entry appears in a
  flash map, we strip it off the image, and use ifdtool to place the rest
  of the image into a provided skeleton file (which contains the management
  engine and a skeleton firmware descriptor).
  """
  def __init__(self, props):
    super(EntryIfd, self).__init__(props)

  def ProduceFinalImage(self, tools, out, tmpdir, image_fname):
    """Produce the final image for an Intel ME system

    Some Intel systems require that an image contains the Management Engine
    firmware, and also a firmware descriptor.

    This function takes the existing image, removes the front part of it,
    and replaces it with these required pieces using ifdtool.

    Args:
      tools: Tools object to use to run tools.
      out: Output object to send output to
      tmpdir: Temporary directory to use to create required files.
      image_fname: Output image filename
    """
    out.Progress('Setting up Intel ME')
    data = tools.ReadFile(image_fname)

    # We can assume that the ifd section is at the start of the image.
    if self.offset != 0:
      raise ConfigError('IFD section must be at offset 0 in the image')
    data = data[self.size:]
    input_fname = os.path.join(tmpdir, 'ifd-input.bin')
    tools.WriteFile(input_fname, data)
    ifd_output = os.path.join(tmpdir, 'image.ifd')

    # This works by modifying a skeleton file.
    shutil.copyfile(tools.Filename(self.pack.props['skeleton']), ifd_output)
    args = ['-i', 'BIOS:%s' % input_fname, ifd_output]
    tools.Run('ifdtool', args)

    # ifdtool puts the output in a file with '.new' tacked on the end.
    shutil.move(ifd_output + '.new', image_fname)
    tools.OutputSize('IFD image', image_fname)

class EntryBlob(EntryFmapArea):
  """This entry contains a binary blob.

  Properties:
    self.value: The filename to read to obtain the blob data.
  """
  def __init__(self, props, params):
    super(EntryBlob, self).__init__(props)
    self.params = params
    if 'compress' not in self:
      self.compress = None
    self.with_index = 'with_index' in props

  def GetData(self):
    return self.pack.tools.ReadFileAndConcat(
        self.value, self.compress, self.with_index)[0]


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
    self._CheckFieldsInt(('version', 'preamble_flags'))
    if 'compress' not in self:
      self.compress = None
    self.with_index = 'with_index' in props

# pylint can't figure out that self.value is set by now
#pylint: disable=E0203

  def RunTools(self, tools, out, tmpdir):
    """Create a vblock for the given firmware image"""
    self.path = os.path.join(tmpdir, 'vblock.%s' % self.label)
    input_data = os.path.join(tmpdir, 'input.%s' % self.label)
    try:
      prefix = self.pack.props['keydir'] + '/'

      # Join up the data files to be signed
      data = self.pack.tools.ReadFileAndConcat(
        self.value, self.compress, self.with_index)[0]
      tools.WriteFile(input_data, data)
      args = [
          '--vblock', self.path,
          '--keyblock', prefix + self.keyblock,
          '--signprivate', prefix + self.signprivate,
          '--version', '%d' % self.version,
          '--fv', input_data,
          '--kernelkey', prefix + self.kernelkey,
          '--flags', '%d' % self.preamble_flags,
      ]
      out.Notice("Sign '%s' into %s" % (', '.join(self.value), self.label))
      stdout = tools.Run('vbutil_firmware', args)
      out.Debug(stdout)

      # Update value to the actual filename to be used
      self.value = [self.path]
    except CmdError as err:
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
  def __init__(self, tools, output):
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
    self._out = output
    self.tools = tools

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
      node: The node to use, e.g. /flash/ro-stub
      props: Doctionary containing all properties from the node.

    Returns:
      An entry set up and ready for packing.

    Raises:
      ValueError: If fdt has an unknown entry type.
    """
    entry_list = props.get('type', 'empty').split()
    ftype = entry_list[0]
    if ftype == 'empty':
      ftype = ''
    key = None
    if len(entry_list) > 1:
      key = entry_list[1]
    params = entry_list[2:]

    # Create an entry of the correct type.
    entry = None
    if not ftype:
      entry = EntryFmapArea(props)
    elif ftype == 'blob':
      entry = EntryBlob(props, params)
    elif ftype == 'wiped':
      entry = EntryWiped(props)
    elif ftype == 'keyblock':
      entry = EntryKeyBlock(props)
    elif ftype == 'blobstring':
      entry = EntryBlobString(props)
    elif ftype == 'fmap':
      entry = EntryFmap(props)
    elif ftype == 'ifd':
      entry = EntryIfd(props)
    elif ftype == 'fdtmap':
      entry = EntryFdtMap(props)
    else:
      raise ValueError('%s: unknown entry type' % ftype)

    entry.pack = self
    entry.node = node
    entry.key = key
    entry.required = 'required' in props
    entry.ftype = ftype
    return entry

  def _IsRequired(self, entry):
    """Check if an entry is required in the final image.

    Args:
      entry: Entry to check

    Returns:
      True if this entry must be included, False if not.
    """
    return entry.required

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

    Returns:
      True if all entries are required in the image, else False
    """
    required = filter(self._IsRequired, self.entries)
    entries = sorted(required, key=lambda e: e.offset)
    all_entries = len(self.entries) == len(required)
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
        self._out.Warning('Warning: Flash map has a gap of %d bytes: '
            '%s: %08x-%08x, %s: %08x-%08x' %
            (-overlap, e1.label, e1.offset, e1.offset + e1.size,
             e2.label, e2.offset, e2.offset + e2.size))

    return all_entries

  def SelectFdt(self, fdt, board=None, default_flashmap=None):
    """Scan FDT and build entry objects.

    This creates a list of entry objects which we can later use to generate
    a firmware image. Each entry's properties are set up correcty but at this
    stage no data is processed. The result is a list of entries in
    self.entries.

    Args:
      fdt: fdt object containing the device tree.
      board: Name of board type if known (None if not known).
      default_flashmap: A default flash map for the current board, or None if
          not available. This is a list of dictionaries, each of which is
          the properties for a single node. For example this one has a single
          node:

              [{
              'node' : 'ro-boot',
              'label' : 'boot-stub',
              'size' : 512 << 10,
              'read-only' : True,
              'type' : 'blob signed',
              'required' : True
              }]

          The default flash map is only used if the fdt does not have one.
          This is typically the case when booting an upstream U-Boot, which
          does not have a Chrome OS flashmap.

    Raises:
      ConfigError if an error is detected in the fdt configuration.
    """
    def _AddNode(node, props):
      """Add a new flash map node to the entry list.

      Args:
        node: Name of node to read from
        props: Dictionary containing properties of the node
      """
      align = int(props.get('align', '1'))
      align_mask = align - 1
      if align == 0 or (align & align_mask) != 0:
        raise ValueError("Invalid alignment %d in node '%s'" % props['label'])
      # Read the two cells from the node's /reg property to get entry extent.
      reg = props.get('reg', None)
      if reg:
        offset, size = fdt.DecodeIntList(node, 'reg', reg, 2)
        if (offset & align_mask) or (size & align_mask):
          raise ValueError("Alignment of %d conflicts with 'reg' setting in"
                           "node '%s': offset=%#08x, size=%#08x" %
                           (align, props['label'], offset, size))
      else:
        size = props.get('size', None)
        if not size:
          raise ValueError("Must specify either 'reg' or 'size' in flash"
                           "node '%s'" % props['label'])
        size = int(size)
        offset = self.upto_offset
        offset = (offset + align_mask) & ~align_mask

      props['node'] = node
      props['offset'] = offset
      props['size'] = size

      # The section names must be upper case with underscores, for other tools
      props['name'] = re.sub('-', '_', props['label']).upper()
      props['flags'] = self._GetFlags(props)
      try:
        entry = self._CreateEntry(node, props)
        self.entries.append(entry)

      except ConfigError as err:
        raise ValueError('Config error: %s' % err)

      if entry.ftype:
        self.upto_offset = offset + size
      else:
        self.upto_offset = offset
      if entry.required:
        self.required_count += 1
      if entry.key == 'signed':
        self.first_blob_entry = entry

    self.fdt = fdt
    root = '/flash'

    # Current offset to use for entries with only a 'size' property.
    self.upto_offset = 0
    self.required_count = 0
    self.first_blob_entry = None

    # If we don't have a flash map, invent a Tegra one
    # TODO(sjg@chromium.org): Make this work with other SOCs also
    if not fdt.GetProp(root, 'reg', ''):
      if not default_flashmap:
        raise ValueError("No /flash present in fdt, and no available default"
                         " for board '%s'" % board)
      self._out.Warning("Warning: No /flash present in fdt - using default"
                        " for board '%s'" % board)
      self.image_size = 0
      for fmap_item in default_flashmap:
        _AddNode(root + '/' + fmap_item['node'], fmap_item)
        self.image_size += fmap_item['size']

    else:
      self.image_size = int(fdt.GetIntList(root, 'reg', 2)[1])

      # Scan the flash map in the fdt, creating a list of Entry objects.
      children = fdt.GetChildren(root)

      for child in children:
        node = root + '/' + child
        props = fdt.GetProps(node, True)

        _AddNode(node, props)

        # If there was only a 'size' property, write a full 'reg' property
        # based on the offset we calculated
        if not props.get('reg'):
          fdt.PutIntList(node, 'reg', [props['offset'], props['size']])

    # HACK: Since Tegra FDT files are not in our tree yet, but we still want
    # to use the old ones, we emulate the old behavior by marking the signed
    # entry as required, if none of the entries were marked required.
    if not self.required_count:
      self.first_blob_entry.required = True

  def GetBlobList(self):
    """Generate a list of blob types that we are going to need.

    Returns:
      List of blob type strings
    """
    blob_set = set()
    for entry in self.entries:
      if isinstance(entry, EntryBlob):
        blob_set.update(entry.key.split(','))

    return list(blob_set)

  def GetBlobParams(self, blob_type):
    """Returns the parameters for a blob of the given type.

    There should be only one blob of this type.

    Args:
      blob_type: Type of the blob (e.g. 'exynos-bl2')

    Raises:
      ValueError if the blob cannot be found.

    Returns:
      The list of parameters for this blob, which may be empty
    """
    for entry in self.entries:
      if isinstance(entry, EntryBlob):
        if entry.key == blob_type:
          return entry.params

    raise ValueError("Blob type '%s' cannot be found" % blob_type)

  def AddProperty(self, name, value):
    """Add a new property which can be used by the fdt.

    Args:
      name: Name of property
      value: Value of property (typically a filename)
    """
    if not value:
      raise CmdError("Cannot find value for entry property '%s'" % name)
    self.props[name] = value

  def GetProperty(self, name):
    """Get the value of a property required by the fdt.

    Args:
      name: Name of property

    Returns:
      Value of property, normally a filename string
    """
    return self.props.get(name, None)

  def ConcatPropContents(self, prop_list, compress, with_index):
    """Read, concatenate and return the contents of the listed props.

    Each property references a filename. We read the contents of each
    file and join it together.

    Each section starts on a 32-bit boundary.

    Args:
      prop_list: List of properties to process
      compress: compression type, like 'lzo', None for no compression
      with_index: Wether an index structure should be prepended
          See ReadFileAndConcat for more details.

    Returns:
      Tuple:
        Contents of the files (as a string), optionally with an index
          prepended (see ReadFileAndConcat for details)
        Directory of the position of the contents, as a dictionary:
          key: Name of the property
          value: List containing:
            offset of the start of this property's data
            size of this property's data
    """
    filenames = [self.props[prop] for prop in prop_list]
    data, offset, length = \
        self.tools.ReadFileAndConcat(filenames, compress, with_index)
    directory = {}
    for i in xrange(len(prop_list)):
      directory[prop_list[i]] = [offset[i], length[i]]
    return data, directory

# For some weird reason pylint presumes that sha256 is not in hashlib
#pylint: disable=E1101

  def UpdateBlobPositionsAndHashes(self, fdt):
    """Record position and size of all blob members in the FDT.

    Some blobs have multiple files within them. We want a way to
    access these individiually. We do this by adding a subnode for
    each, and putting the offset and size information in there.

    This function scans for blobs with more than one file and adds
    a 'reg' property to the subnode for each file. It also adds 'hash'
    nodes with the sha 256 hash of the file's contents.

    Note: Since one of the members may in fact be the fdt, and we are
    updating the fdt, we may change the size it. To get around this,
    we perform two passes of the algorithm. On the second pass we will
    be writing data that is already there, so the fdt size will not
    change.
    """
    for _ in range(0, 2):
      for entry in self.entries:
        if isinstance(entry, EntryBlob):
          self._out.Info("Updating blob positions in fdt for '%s'" % entry.key)
          data, directory = self.ConcatPropContents(
              entry.key.split(','), None, entry.with_index)
          if len(directory) > 1:
            fdt.PutInteger(entry.node, '#address-cells', 1)
            fdt.PutInteger(entry.node, '#size-cells', 1)
            for key, item in directory.iteritems():
              fdt.PutIntList(entry.node + '/' + key, 'reg', item)
              hasher = hashlib.sha256()
              offset, size = item
              hasher.update(data[offset:offset + size])
              hash_value = hasher.digest()
              byte_count = struct.unpack('%dB' % len(hash_value), hash_value)
              fdt.PutBytes(entry.node + '/' + key, 'hash', byte_count)

  def CheckProperties(self):
    """Check that each entry has the properties that it needs.

    Entries with a 'key' use that to look up properties. We need to make
    sure that there is a property for that key. If not, then the entry will
    not be able to access the data it needs during the packing stage.

    Raises:
      ConfigError: The property for a required key is missing
    """
    for entry in self.entries:
      if entry.required and entry.key:
        if 'value' not in entry:
          entry.value = []
        for prop in entry.key.split(','):
          if not self.props.get(prop):
            raise ConfigError("%s: Requests property '%s' but we only "
                "have %s" % (entry.node, prop, self.props.keys()))
          entry.value.append(self.props[prop])

  def RequireAllEntries(self):
    """Mark all entries as required, to produce a full image."""
    for entry in self.entries:
      entry.required = True

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

    all_entries = self._CheckOverlap()
    image_used = 0

    # Set up a zeroed file of the correct size.
    with open(output_path, 'wb') as image:
      if all_entries:
        image.write('\0' * self.image_size)

      # Pack all the entriess.
      ifd = None
      for entry in self.entries:
        if not entry.required:
          self._out.Info("Section '%s' is not required, skipping" % entry.name)
          continue

        # Add in the info for the fmap.
        if type(entry) == EntryFmap:
          entry.SetEntries(base=0, image_size=self.image_size,
              entries=self.entries)
        elif type(entry) == EntryIfd:
          ifd = entry

        try:
          # First run any required tools.
          entry.RunTools(self.tools, self._out, self.tmpdir)
          if 'value' in entry:
            self._out.Notice("Pack '%s' into %s" % (', '.join(entry.value),
                entry.name))

          # Now read out the data
          data = entry.GetData()
          self._out.Debug('Entry: %s' % entry.name)
          self._out.Debug('Entry data: %s' % entry)
          self._out.Debug('Data size: %s bytes, at %#x' %
              (len(data), entry.offset))
          if len(data) > entry.size:
            raise PackError("Data for '%s' too large for area: %d/%#x >"
                " %d/%#x" % (entry.name, len(data), len(data), entry.size,
                entry.size))
          if entry.size:
            usage = len(data) * 100 / entry.size
          else:
            usage = 0
          self._out.Notice('Entry: %s, size %#x, data %#x, usage %d%%' %
              (entry.name, entry.size, len(data), usage))
          entry.used = len(data)
          image_used += entry.used

          image.seek(entry.offset)
          image.write(data)

        except PackError as err:
          raise ValueError('Packing error: %s' % err)

    # If the image contain an IFD section, process it
    if ifd:
      ifd.ProduceFinalImage(self.tools, self._out, self.tmpdir, output_path)

    self._out.Notice('Image size %#x, data %#x, usage %d%%' %
      (self.image_size, image_used, image_used * 100 / self.image_size))

  def _OutEntry(self, status, offset, size, name):
    """Display a flash map entry.

    Args:
      status: Status character.
      offset: Byte offset of entry.
      size: Size of entry in bytes.
      name: Name of entry.
    """
    indent = '' if status == '-' else ' '
    self._out.UserOutput('%s %08x  %08x  %s%-20s' % (status, offset, size,
        indent, name))

  def ShowMap(self):
    """Show a map of the final image."""
    self._out.UserOutput('Final Flash Map:')
    self._out.UserOutput('%s %8s  %8s  %-20s' % ('S', 'Start', 'Size', 'Name'))
    offset = 0
    for entry in self.entries:
      if not entry.ftype:
        status = '-'
      elif entry.required:
        status = 'P'
      else:
        status = '.'
      if offset != entry.offset:
        self._OutEntry('!', offset, entry.offset - offset, '<gap>')
      self._OutEntry(status, entry.offset, entry.size, entry.name)
      if entry.ftype:
        offset = entry.offset + entry.size
      else:
        offset = entry.offset

def _Test():
  """Run any built-in tests."""
  import doctest
  assert doctest.testmod().failed == 0

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

  (options, _) = parser.parse_args(sys.argv)

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
