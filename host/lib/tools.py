#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This implements calling of scripts and other utilities/tools.

We support running inside and outside the chroot. To do this, we permit
a ## prefix which resolves to the chroot. Within the chroot this will be
/ but outside it will be the full path to the chroot.

So we can use filenames like this:

    ##/usr/share/vboot/bitmaps/make_bmp_images.sh

"""

import doctest
import optparse
import os
import re
import shutil
import struct
import sys
import tempfile
import unittest

from chromite.lib import cros_build_lib
from chromite.lib import git
import cros_output

# Attributes defined outside __init__
#pylint: disable=W0201

class CmdError(Exception):
  """An error in the execution of a command."""
  pass


class Tools:
  """A class to encapsulate the external tools we want to run.

  This provides convenient functions for running tools inside/outside the
  chroot.

  Public properties:
    outdir: The output directory to write output files to.
    search_paths: The list of directories to search for files we are asked
        to read.

  The tools class also provides common paths:

    chroot_path: chroot directory
    src_path: source directory
    script_path: scripts directory (src/scripts)
    overlay_path: overlays directory (src/overlays)
    priv_overlay_path: private overlays directory (src/private-overlays)
    board_path: build directory (/build in chroot)
    third_party_path: third_parth directory (src/third_party)
    cros_overlay_path: Chromium OS overlay (src/chromiumos-overlay)
  """

  def __init__(self, output):
    """Set up the tools system.

    Args:
      output: cros_output object to use for output.

    Raises:
      IOError: Unable to find .repo directory

    """
    # Detect whether we're inside a chroot or not
    self.in_chroot = cros_build_lib.IsInsideChroot()
    self._out = output
    self._root = None
    if self.in_chroot:
      root_dir = os.getenv('CROS_WORKON_SRCROOT')
    else:
      repo = git.FindRepoDir('.')
      if not repo:
        raise IOError('Cannot find .repo directory (must be below cwd level)')
      root_dir = os.path.dirname(repo)
    self._SetRoot(root_dir)

    self._out.Info("Chroot is at '%s'" % self.chroot_path)
    self._tools = {
      'make_bmp_image': '##/usr/share/vboot/bitmaps/make_bmp_images.sh',
      'bct_dump': '##/usr/bin/bct_dump',
      'tegrarcm': '##/usr/bin/tegrarcm',
      'gbb_utility': '##/usr/bin/gbb_utility',
      'cbfstool': '##/usr/bin/cbfstool',
      'fdisk': '##/sbin/fdisk',
    }
    self.outdir = None            # We have no output directory yet
    self.search_paths = []

  def __enter__(self):
    return self

  def __exit__(self, the_type, value, traceback):
    self.FinalizeOutputDir()
    return False

  def _SetRoot(self, root_dir):
    """Sets the root directory for the build envionrment.

    The root directory is the one containing .repo, chroot and src.

    This should be called once the root is known. All other parts are
    calculated from this.

    Args:
      root_dir: The path to the root directory.
    """
    self._root = os.path.normpath(root_dir)

    # Set up the path to prepend to get to the chroot
    if self.in_chroot:
      self.chroot_path = '/'
    else:
      self.chroot_path = os.path.join(self._root, 'chroot')
    self.src_path = os.path.join(self._root, 'src')
    self.script_path = os.path.join(self.src_path, 'scripts')
    self.overlay_path = os.path.join(self.src_path, 'overlays')
    self.priv_overlay_path = os.path.join(self.src_path,
                                          'private-overlays')
    self.board_path = os.path.join(self.chroot_path, 'build')
    self.third_party_path = os.path.join(self.src_path, 'third_party')
    self.cros_overlay_path = os.path.join(self.third_party_path,
                                          'chromiumos-overlay')

  def Filename(self, fname):
    """Resolve a chroot-relative filename to an absolute path.

    This looks for ## at the beginning of the filename, and changes it to
    the chroot directory, which will be / if inside the chroot, or a path
    to the chroot if not.

    Args:
      fname: Filename to convert.

    Returns:
      Absolute path to filename.
    """
    if fname.startswith('##/'):
      fname = os.path.join(self.chroot_path, fname[3:])

    # Search for a pathname that exists, and return it if found
    if fname and not os.path.exists(fname):
      for path in self.search_paths:
        pathname = os.path.join(path, os.path.basename(fname))
        if os.path.exists(pathname):
          return pathname

    # If not found, just return the standard, unchanged path
    return fname

  def Run(self, tool, args, cwd=None, sudo=False):
    """Run a tool with given arguments.

    The tool name may be used unchanged or substituted with a full path if
    required.

    The tool and arguments can use ##/ to signify the chroot (at the beginning
    of the tool/argument).

    Args:
      tool: Name of tool to run.
      args: List of arguments to pass to tool.
      cwd: Directory to change into before running tool (None if none).
      sudo: True to run the tool with sudo

    Returns:
      Output of tool (stdout).

    Raises:
      CmdError: If running the tool, or the tool itself creates an error.
    """
    if tool in self._tools:
      tool = self._tools[tool]
    tool = self.Filename(tool)
    args = [self.Filename(arg) for arg in args]
    cmd = [tool] + args
    if sudo:
      cmd.insert(0, 'sudo')
    try:
      result = cros_build_lib.RunCommandCaptureOutput(
          cmd, cwd=cwd, print_cmd=self._out.verbose > 3,
          combine_stdout_stderr=True, error_code_ok=True)
    except cros_build_lib.RunCommandError as ex:
      raise CmdError(str(ex))
    stdout = result.output
    if result.returncode:
      raise CmdError('Command failed: %s\n%s' % (' '.join(cmd), stdout))
    self._out.Debug(stdout)
    return stdout

  def ReadFile(self, fname):
    """Read and return the contents of a file.

    Args:
      fname: path to filename to read, where ## signifiies the chroot.

    Returns:
      data read from file, as a string.
    """
    fd = open(self.Filename(fname), 'rb')
    data = fd.read()
    fd.close()
    self._out.Info("Read file '%s' size %d (%#0x)" %
                   (fname, len(data), len(data)))
    return data

  def WriteFile(self, fname, data):
    """Write data into a file.

    Args:
      fname: path to filename to write, where ## signifiies the chroot.
      data: data to write to file, as a string.
    """
    self._out.Info("Write file '%s' size %d (%#0x)" %
                   (fname, len(data), len(data)))
    fd = open(self.Filename(fname), 'wb')
    fd.write(data)
    fd.close()

  def ReadFileAndConcat(self, filenames, compress=None, with_index=False):
    """Read several files and concat them.

    Args:
      filenames: a list containing name of the files to read.
      with_index: If true, an index structure is prepended to the data.

    Returns:
      A tuple of a string and two list. The string is the concated data read
        from file, in the same order as in filenames, aligned to 4-byte. The
        first list contains the offset of each file in the data string and
        the second one contains the actual (non-padded) length of each file,
        both in the same order.

        The optional index structure is a 32 bit integer set to the number of
        entries in the index, followed by that many pairs of integers which
        describe the offset and length of each chunk.
    """
    data = ''
    offsets = []
    lengths = []
    for fname in filenames:
      offsets.append(len(data))
      content = self.ReadFile(fname)
      pad_len = ((len(content) + 3) & ~3) - len(content)
      data += content + chr(0xff) * pad_len
      lengths.append(len(content))

    if with_index:
      index_size = 4 + len(filenames) * 8
      index = struct.pack("<I", len(filenames))
      offsets = tuple(offset + index_size for offset in offsets)
      for _, offset, length in zip(filenames, offsets, lengths):
        index += struct.pack("<II", offset, length)
      data = index + data

    if compress:
      if compress == 'lzo':
        # Would be nice to just pipe here. but we don't have RunPipe().
        fname = self.GetOutputFilename('data.tmp')
        outname = self.GetOutputFilename('data.tmp.lzo')
        if os.path.exists(outname):
          os.remove(outname)
        self.WriteFile(fname, data)
        args = ['-9', fname]
        self.Run('lzop', args)
        data = self.ReadFile(outname)
      else:
        raise ValueError("Unknown compression method '%s'" % compress)
    return data, offsets, lengths

  def GetChromeosVersion(self):
    """Returns the ChromeOS version string.

    This works by finding and executing the version script:

    src/third_party/chromiumos-overlay/chromeos/config/chromeos_version.sh

    Returns:
      Version string in the form '0.14.726.2011_07_07_1635'

    Raises:
      CmdError: If the version script cannot be found, or is found but cannot
          be executed.
    """
    version_script = os.path.join(self.cros_overlay_path, 'chromeos', 'config',
                                  'chromeos_version.sh')

    if os.path.exists(version_script):
      result = self.Run('sh', ['-c', '. %s >/dev/null; '
                               'echo ${CHROMEOS_VERSION_STRING}'
                               % version_script])
      return result.strip()
    raise CmdError("Cannot find version script 'chromeos_version.sh'")

  def CheckTool(self, name, ebuild=None):
    """Check that the specified tool exists.

    If it does not exist in the PATH, then generate a useful error message
    indicating how to install the ebuild that contains the required tool.

    Args:
      name: filename of tool to look for on path.
      ebuild: name of ebuild which should be emerged to install this tool,
          or None if it is the same as the filename.

    Raises:
      CmdError(msg) if the tool is not found.
    """
    try:
      filename = name
      if filename in self._tools:
        filename = self._tools[filename]
      filename = self.Filename(filename)
      self.Run('which', [filename])
    except CmdError:
      raise CmdError("The '%s' utility was not found in your path. "
                     "Run the following command in \nyour chroot to install "
                     "it: sudo -E emerge %s" % (filename, ebuild or name))

  def OutputSize(self, label, filename, level=cros_output.NOTICE):
    """Display the filename and size of an object.

    Args:
      label: Label for this file.
      filename: Filename to output.
      level: Verbosity level to attach to this message
    """
    filename = self.Filename(filename)
    size = os.stat(filename).st_size
    self._out.DoOutput(level, '%s: %s; size: %d / %#x' %
                       (label, filename, size, size))

  def PrepareOutputDir(self, outdir, preserve=False):
    """Select an output directory, ensuring it exists.

    This either creates a temporary directory or checks that the one supplied
    by the user is valid. For a temporary directory, it makes a note to
    remove it later if required.

    Args:
      outdir: a string, name of the output directory to use to store
              intermediate and output files. If is None - create a temporary
              directory.
      preserve: a Boolean. If outdir above is None and preserve is False, the
                created temporary directory will be destroyed on exit.
    Raises:
      OSError: If it cannot create the output directory.
    """
    self.preserve_outdir = outdir or preserve
    if outdir:
      self.outdir = outdir
      if not os.path.isdir(self.outdir):
        try:
          os.makedirs(self.outdir)
        except OSError as err:
          raise CmdError("Cannot make output directory '%s': '%s'" %
                         (self.outdir, err.strerror))
    else:
      self.outdir = tempfile.mkdtemp(prefix='cros-dev.')
      self._out.Debug("Using temporary directory '%s'" % self.outdir)

  def FinalizeOutputDir(self):
    """Tidy up: delete output directory if temporary and not preserved."""
    if self.outdir and not self.preserve_outdir:
      shutil.rmtree(self.outdir)
      self._out.Debug("Deleted temporary directory '%s'" %
                      self.outdir)
      self.outdir = None

  def GetOutputFilename(self, fname):
    """Return a filename within the output directory.

    Args:
      fname: Filename to use for new file

    Returns:
      The full path of the filename, within the output directory
    """
    return os.path.join(self.outdir, fname)


# pylint: disable=W0212
class ToolsTests(unittest.TestCase):
  """Unit tests for this module."""

  def setUp(self):
    self.out = cros_output.Output(False)
    self.tools = Tools(self.out)

  def MakeOutsideChroot(self, base):
    tools = Tools(self.out)
    tools.in_chroot = False
    tools._SetRoot(base)
    return tools

  def testPaths(self):
    tools = self.tools

    self.assertTrue(os.path.isdir(os.path.join(tools._root, '.repo')))

  def _testToolsPaths(self, base, tools):
    """Common paths tests to run inside and outside chroot.

    These tests are the same inside and outside the choot, so we put them in a
    separate function.

    Args:
      base: Base directory to use for testing (contains the 'src' directory).
      tools: Tools object to use.
    """
    self.assertEqual(tools._root, base[:-1])
    self.assertEqual(tools.src_path, base + 'src')
    self.assertEqual(tools.script_path, base + 'src/scripts')
    self.assertEqual(tools.overlay_path, base + 'src/overlays')
    self.assertEqual(tools.priv_overlay_path, base + 'src/private-overlays')
    self.assertEqual(tools.third_party_path, base + 'src/third_party')
    self.assertEqual(tools.cros_overlay_path, base +
                     'src/third_party/chromiumos-overlay')

  def testSetRootInsideChroot(self):
    """Inside the chroot, paths are slightly different from outside."""
    tools = Tools(self.out)
    tools.in_chroot = True

    # Force our own path.
    base = '/air/bridge/'
    tools._SetRoot(base)

    # We should get a full path from that without the trailing '/'.
    self.assertEqual(tools.chroot_path, '/')
    self.assertEqual(tools.board_path, '/build')
    self._testToolsPaths(base, tools)

  def testSetRootOutsideChroot(self):
    """Pretend to be outside the chroot, and check that paths are correct."""

    # Force our own path, outside the chroot.
    base = '/spotty/light/'
    tools = self.MakeOutsideChroot(base)

    # We should get a full path from that without the trailing '/'.
    self.assertEqual(tools.chroot_path, base + 'chroot')
    self.assertEqual(tools.board_path, tools.chroot_path + '/build')
    self._testToolsPaths(base, tools)

  def _testToolsFilenames(self, tools):
    """Common filename tests to run inside and outside chroot.

    These tests are the same inside and outside the choot, so we put them in a
    separate function.

    Args:
      tools: Tools object to use.
    """
    self.assertEqual(tools.Filename('/root/based/'),
                     '/root/based/')

    # Try search paths in /bin and /ls.
    tools.search_paths = ['/bin', '/lib']
    file_in_bin = os.listdir('/bin')[0]
    self.assertEqual(tools.Filename(file_in_bin), '/bin/%s' % file_in_bin)
    file_in_lib = os.listdir('/lib')[0]
    self.assertEqual(tools.Filename(file_in_lib), '/lib/%s' % file_in_lib)
    self.assertEqual(tools.Filename('i-am-not-here'), 'i-am-not-here')

    # Don't search for an empty file.
    self.assertEqual(tools.Filename(''), '')

  def testFilenameInsideChroot(self):
    """Test that we can specify search paths and they work correctly.

    Test search patches inside the chroot.
    """
    tools = Tools(self.out)
    tools.in_chroot = True

    # Force our own path.
    base = '/air/bridge/'
    tools._SetRoot(base)

    self.assertEqual(tools.Filename('##/fred'), '/fred')
    self.assertEqual(tools.Filename('##/just/a/short/dir/'),
                     '/just/a/short/dir/')

    self._testToolsFilenames(tools)

  def testFilenameOutsideChroot(self):
    """Test that we can specify search paths and they work correctly.

    Test search patches outside the chroot.
    """
    base = '/home/'
    tools = self.MakeOutsideChroot(base)

    self.assertEqual(tools.Filename('##/fred'), base + 'chroot/fred')
    self.assertEqual(tools.Filename('##/just/a/short/dir/'),
                     base + 'chroot/just/a/short/dir/')

    self._testToolsFilenames(tools)

  def testReadWriteFile(self):
    """Test our read/write utility functions."""
    tools = Tools(self.out)
    tools.PrepareOutputDir(None)
    data = 'some context here' * 2

    fname = tools.GetOutputFilename('bang')
    tools.WriteFile(fname, data)

    # Check that the file looks correct.
    compare = tools.ReadFile(fname)
    self.assertEqual(data, compare)

  def testReadFileAndConcat(self):
    """Test 'cat' of several files."""
    tools = Tools(self.out)
    tools.PrepareOutputDir(None)
    file_list = ['one', 'empty', 'two', 'three', 'four']
    out_list = [tools.GetOutputFilename(fname) for fname in file_list]
    file_list[1] = ''   # Empty the 'empty' file.
    for upto in range(len(file_list)):
      tools.WriteFile(out_list[upto], file_list[upto])

    data, offset, length = tools.ReadFileAndConcat(out_list)
    self.assertEqual(len(data), 20)
    self.assertEqual(offset, [0, 4, 4, 8, 16])
    self.assertEqual(length, [3, 0, 3, 5, 4])

  def testGetChromeosVersion(self):
    """Test for GetChromeosVersion() inside and outside chroot.

    This function returns a string like '2893.0.2012_09_16_2219'.
    """
    tools = self.tools

    re_version = re.compile('\d{4}.\d+.\d{4}_\d{2}_\d{2}_\d+')
    self.assertTrue(re_version.match(tools.GetChromeosVersion()))

    tools = Tools(self.out)

    # Force our own path, outside the chroot. This should fail.
    base = 'invalid-dir'
    tools = self.MakeOutsideChroot(base)
    tools.in_chroot = False
    self.assertRaises(CmdError, tools.GetChromeosVersion)

  def testCheckTool(self):
    """Test for the CheckTool() method."""
    tools = self.tools

    tools.CheckTool('fdisk')
    tools.CheckTool('gbb_utility')
    self.assertRaises(CmdError, tools.CheckTool, 'non-existent-tool')
    tools.CheckTool('fdisk')
    self.assertRaises(CmdError, tools.CheckTool, '/usr/bin/fdisk')

  def testRun(self):
    """Test for the Run() method."""
    tools = self.tools

    # Ask fdisk for its version - this utility must be in the chroot.
    re_fdisk = re.compile('fdisk \(util-linux .*\)')
    self.assertTrue(re_fdisk.match(tools.Run('fdisk', ['-v'])))

    # We need sudo for looking at disks.
    self.assertEqual(tools.Run('fdisk', ['-l', '/dev/sda']),
                     'Cannot open /dev/sda\n')
    out = tools.Run('fdisk', ['-l', '/dev/sda'], sudo=True)

    #  Don't look at the specific output, but it will have > 5 lines.
    self.assertTrue(len(out.splitlines()) > 5)

    self.assertEqual(tools.Run('pwd', [], cwd='/tmp'), '/tmp\n')

  def testOutputDir(self):
    """Test output directory creation and deletion."""
    tools = self.tools

    # First check basic operation, creating and deleting a tmpdir.
    tools.PrepareOutputDir(None)
    fname = tools.GetOutputFilename('fred')
    tools.WriteFile(fname, 'You are old, Father William, the young man said')
    dirname = tools.outdir
    tools.FinalizeOutputDir()
    self.assertFalse(os.path.exists(fname))
    self.assertFalse(os.path.exists(dirname))

    # Try preserving it.
    tools.PrepareOutputDir(None, True)
    fname = tools.GetOutputFilename('fred')
    tools.WriteFile(fname, 'and your hair has become very white')
    dirname = tools.outdir
    tools.FinalizeOutputDir()
    self.assertTrue(os.path.exists(fname))
    self.assertTrue(os.path.exists(dirname))
    shutil.rmtree(dirname)

    # Use our own directory, which is always preserved.
    testdir = '/tmp/tools-test.test'
    tools.PrepareOutputDir(testdir)
    fname = tools.GetOutputFilename('fred')
    tools.WriteFile(fname, 'and yet you incessantly stand on your head')
    dirname = tools.outdir
    tools.FinalizeOutputDir()
    self.assertTrue(os.path.exists(fname))
    self.assertTrue(os.path.exists(dirname))
    shutil.rmtree(dirname)

    # Try creating an invalid directory.
    testdir = '/sys/cannot/do/this/here'
    self.assertRaises(CmdError, tools.PrepareOutputDir, testdir)
    fname = tools.GetOutputFilename('fred')
    self.assertRaises(IOError, tools.WriteFile, fname,
                      'do you think at your age it is right?')
    dirname = tools.outdir
    tools.FinalizeOutputDir()

  def _OutputMock(self, level, msg, color=None):
    self._level = level
    self._msg = msg
    self._color = color

  def testOutputSize(self):
    """Test for OutputSize() function."""
    tools = self.tools

    # Rather than mocks, use a special Output object.
    out = tools._out
    out._Output = self._OutputMock

    tools.PrepareOutputDir(None)
    fname = tools.GetOutputFilename('fred')
    text_string = 'test of output size'
    tools.WriteFile(fname, text_string)

    re_fname = re.compile('fred')
    re_size = re.compile('.*size: (\d*)')

    tools.OutputSize('first', fname, level=cros_output.ERROR)
    self.assertEqual(self._level, cros_output.ERROR)
    self.assertTrue(re_fname.search(self._msg))
    self.assertEqual(self._color, None)

    # Check the default level, and that the filename length is given.
    tools.OutputSize('second', fname)
    self.assertEqual(self._level, cros_output.NOTICE)
    self.assertTrue(re_fname.search(self._msg))
    self.assertEqual(self._color, None)
    m = re_size.match(self._msg)
    self.assertEqual(m.group(1), str(len(text_string)))

    tools.FinalizeOutputDir()


def _Test(argv):
  """Run any built-in tests."""
  unittest.main(argv=argv)
  assert doctest.testmod().failed == 0


def main():
  """Main function for tools.

  We provide a way to call a few of our useful functions.

  TODO(sjg) Move into the Chromite libraries when these are ready.
  """
  parser = optparse.OptionParser()
  parser.add_option('-v', '--verbosity', dest='verbosity', default=1,
                    type='int',
                    help='Control verbosity: 0=silent, 1=progress, 3=full, '
                    '4=debug')

  help_str = '%s [options] cmd [args]\n\nAvailable commands:\n' % sys.argv[0]
  help_str += '\tchromeos-version\tDisplay Chrome OS version'
  parser.usage = help_str

  (options, args) = parser.parse_args(sys.argv)
  args = args[1:]

  out = cros_output.Output(options.verbosity)
  tools = Tools(out)
  if not args:
    parser.error('No command provided')
  elif args[0] == 'chromeos-version':
    print tools.GetChromeosVersion()
  else:
    parser.error("Unknown command '%s'" % args[0])

if __name__ == '__main__':
  if sys.argv[1:2] == ['--test']:
    _Test([sys.argv[0]] + sys.argv[2:])
  else:
    main()
