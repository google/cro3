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

import optparse
import os
import shutil
import sys
import tempfile

from cros_build_lib import RunCommandCaptureOutput
import cros_build_lib
import cros_output


class CmdError(Exception):
  """An error in the execution of a command."""
  pass


class Tools:
  """A class to encapsulate the external tools we want to run

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
    """
    # Detect whether we're inside a chroot or not
    self.in_chroot = cros_build_lib.IsInsideChroot()
    self._out = output
    self._root = None
    if self.in_chroot:
      root_dir = os.getenv('CROS_WORKON_SRCROOT')
    else:
      repo = cros_build_lib.FindRepoDir()
      if not repo:
        raise IOError('Cannot find .repo directory (must be below cwd level)')
      root_dir = os.path.dirname(repo)
    self._SetRoot(root_dir)

    self._out.Info("Chroot is at '%s'" % self.chroot_path)
    self._tools = {
      'make_bmp_image' : '##/usr/share/vboot/bitmaps/make_bmp_images.sh',
      'bct_dump' : '##/usr/bin/bct_dump',
      'tegrarcm' : '##/usr/bin/tegrarcm',
      'gbb_utility' : '##/usr/bin/gbb_utility',
      'cbfstool' : '##/usr/bin/cbfstool',
      'fdisk' : '##/sbin/fdisk',
    }
    self.outdir = None          # We have no output directory yet
    self._delete_tempdir = None # And no temporary directory to delete
    self.search_paths = []

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
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
      self.chroot_path = cros_build_lib.PrependChrootPath('')
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

    Returns
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

    Raises
      CmdError if running the tool, or the tool itself creates an error"""
    if tool in self._tools:
      tool = self._tools[tool]
    tool = self.Filename(tool)
    args = [self.Filename(arg) for arg in args]
    cmd = [tool] + args
    if sudo:
      cmd.insert(0, 'sudo')
    try:
      rc, stdout, err = RunCommandCaptureOutput(cmd,
          print_cmd=self._out.verbose > 3, cwd=cwd)
    except OSError:
      raise CmdError('Command not found: %s' % (' '.join(cmd)))
    if rc:
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

  def ReadFileAndConcat(self, filenames):
    """Read several files and concat them.

    Args:
      filenames: a list containing name of the files to read.

    Returns:
      A tuple of a string and two list. The string is the concated data read
        from file, in the same order as in filenames, aligned to 4-byte. The
        first list contains the offset of each file in the data string and
        the second one contains the actual (non-padded) length of each file,
        both in the same order.
    """
    data = ''
    offset = []
    length = []
    for fname in filenames:
      offset.append(len(data))
      content = self.ReadFile(fname)
      pad_len = ((len(content) + 3) & ~3) - len(content)
      data += content + chr(0xff) * pad_len
      length.append(len(content))
    return data, offset, length

  def GetChromeosVersion(self):
    """Returns the ChromeOS version string

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
      str = self.Run('sh', ['-c', '. %s >/dev/null; '
          'echo ${CHROMEOS_VERSION_STRING}'
          % version_script])
      return str.strip()
    raise CmdError("Cannot find version script 'chromeos_version.sh'")

  def CheckTool(self, filename, ebuild=None):
    """Check that the specified tool exists.

    If it does not exist in the PATH, then generate a useful error message
    indicating how to install the ebuild that contains the required tool.

    Args:
      filename: filename of tool to look for on path.
      ebuild: name of ebuild which should be emerged to install this tool,
          or None if it is the same as the filename.

    Raises:
      CmdError(msg) if the tool is not found.
    """
    try:
      if filename in self._tools:
        filename = self._tools[filename]
      filename = self.Filename(filename)
      self.Run('which', [filename])
    except CmdError as err:
      raise CmdError("The '%s' utility was not found in your path. "
          "Run the following command in \nyour chroot to install it: "
          "sudo -E emerge %s" % (filename, ebuild or filename))

  def OutputSize(self, label, filename, level=cros_output.NOTICE):
    """Display the filename and size of an object.

    Args:
      label: Label for this file.
      filename: Filename to output.
      level: Verbosity level to attach to this message
    """
    filename = self.Filename(filename)
    size = os.stat(filename).st_size
    self._out.DoOutput(level, "%s: %s; size: %d / %#x" %
        (label, filename, size, size))

  def PrepareOutputDir(self, outdir, preserve=False):
    """Select an output directory, ensuring it exists.

    This either creates a temporary directory or checks that the one supplied
    by the user is valid. For a temporary directory, it makes a note to
    remove it later if required.

    Args:
      outdir: Output directory to use, or None to use a temporary dir.

    Raises:
      OSError: If it cannot create the output directory.
    """
    self.outdir = outdir
    self.preserve_outdir = preserve
    if self.outdir:
      if not os.path.isdir(self.outdir):
        try:
          os.makedirs(self.outdir)
        except OSError as err:
          raise CmdError("Cannot make output directory '%s': '%s'" %
              (self.outdir, err))

    else:
      self.outdir = tempfile.mkdtemp()
      self._delete_tempdir = self.outdir
      self._out.Debug("Using temporary directory '%s'" %
          self._delete_tempdir)

  def FinalizeOutputDir(self):
    """Tidy up the output direcory, deleting it if temporary"""
    if self._delete_tempdir and not self.preserve_outdir:
      shutil.rmtree(self._delete_tempdir)
      self._out.Debug("Deleted temporary directory '%s'" %
          self._delete_tempdir)
      self._delete_tempdir = None
    elif self.outdir:
      self._out.Debug("Output directory '%s'" % self.outdir)

def _Test():
  """Run any built-in tests."""
  import doctest
  doctest.testmod()

def main():
  """Main function for tools.

  We provide a way to call a few of our useful functions.

  TODO(sjg) Move into the Chromite libraries when these are ready.
  """
  parser = optparse.OptionParser()
  parser.add_option('-v', '--verbosity', dest='verbosity', default=1,
      type='int', help='Control verbosity: 0=silent, 1=progress, 3=full, '
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
  if sys.argv[1:2] == ["--test"]:
    _Test(*sys.argv[2:])
  else:
    main()
