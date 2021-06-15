#!/usr/bin/python3

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(1, '../../../')

from python.lib import cmd_util


def ReadFile(path, mode='r'):
  """Read a given file on disk.  Primarily useful for one off small files.

  The defaults are geared towards reading UTF-8 encoded text.

  Args:
    path: The file to read.
    mode: The mode to use when opening the file.  'r' is for text files (see the
      following settings) and 'rb' is for binary files.

  Returns:
    The content of the file, either as bytes or a string (with the specified
    encoding).
  """
  with open(path, 'rb') as f:
    ret = f.read()
    if 'b' not in mode:
      ret = ret.decode('utf-8')
    return ret


def WriteFile(path, content, mode='w', makedirs=False):
  if makedirs:
    os.makedirs(os.path.dirname(path), exist_ok=True)
  else:
    assert(os.path.exists(path))
  with open(path, mode) as f:
    f.write(content)


class TempDirTestCase(unittest.TestCase):
  """Mixin used to give each test a tempdir that is cleansed upon finish."""

  def __init__(self, *args, **kwargs):
    unittest.TestCase.__init__(self, *args, **kwargs)
    self.tempdir = None
    self._tempdir_obj = None

  def setUp(self):
    self.tempdir = tempfile.mkdtemp(prefix='container.test')
    # We must use addCleanup here so that inheriting TestCase classes can use
    # addCleanup with the guarantee that the tempdir will be cleand up _after_
    # their addCleanup has run. TearDown runs before cleanup functions.
    self.addCleanup(self._CleanTempDir)

  def _CleanTempDir(self):
    if self.tempdir is not None:
      shutil.rmtree(self.tempdir)
      self.tempdir = None

  def ExpectRootOwnedFiles(self):
    """Tell us that we may need to clean up root owned files."""
    if self._tempdir_obj is not None:
      self._tempdir_obj.SetSudoRm()

  def assertFileContents(self, file_path, content):
    """Assert that the file contains the given content."""
    read_content = ReadFile(file_path)
    self.assertEqual(read_content, content)

  def assertTempFileContents(self, file_path, content):
    """Assert that a file in the temp directory contains the given content."""
    self.assertFileContents(os.path.join(self.tempdir, file_path), content)

  def ReadTempFile(self, path):
    """Read a given file from the temp directory.

    Args:
      path: The path relative to the temp directory to read.
    """
    return ReadFile(os.path.join(self.tempdir, path))


class OutputTestCase(unittest.TestCase):
  """Base class for cros unit tests with utility methods."""

  # These work with error output from operation module.
  # ERROR_MSG_RE = re.compile(r'^\033\[1;%dm(.+?)(?:\033\[0m)+$' %
  #                           (30 + terminal.Color.RED,), re.DOTALL)
  # WARNING_MSG_RE = re.compile(r'^\033\[1;%dm(.+?)(?:\033\[0m)+$' %
  #                             (30 + terminal.Color.YELLOW,), re.DOTALL)

  def __init__(self, *args, **kwargs):
    """Base class __init__ takes a second argument."""
    unittest.TestCase.__init__(self, *args, **kwargs)
    self._output_capturer = None

  def _GetOutputCapt(self):
    """Internal access to existing OutputCapturer.

    Raises RuntimeError if output capturing was never on.
    """
    if self._output_capturer:
      return self._output_capturer

    raise RuntimeError('Output capturing was never turned on for this test.')

  def _GenCheckMsgFunc(self, prefix_re, line_re):
    """Return boolean func to check a line given |prefix_re| and |line_re|."""
    def _method(line):
      if prefix_re:
        # Prefix regexp will strip off prefix (and suffix) from line.
        match = prefix_re.search(line)

        if match:
          line = match.group(1)
        else:
          return False

      return line_re.search(line) if line_re else True

    if isinstance(prefix_re, str):
      prefix_re = re.compile(prefix_re)
    if isinstance(line_re, str):
      line_re = re.compile(line_re)

    # Provide a description of what this function looks for in a line.  Error
    # messages can make use of this.
    _method.description = None
    if prefix_re and line_re:
      _method.description = ('line matching prefix regexp %r then regexp %r' %
                             (prefix_re.pattern, line_re.pattern))
    elif prefix_re:
      _method.description = (
          'line matching prefix regexp %r' % prefix_re.pattern)
    elif line_re:
      _method.description = 'line matching regexp %r' % line_re.pattern
    else:
      raise RuntimeError('Nonsensical usage of _GenCheckMsgFunc: '
                         'no prefix_re or line_re')

    return _method

  def _ContainsMsgLine(self, lines, msg_check_func):
    return any(msg_check_func(ln) for ln in lines)

  def _GenOutputDescription(self, check_stdout, check_stderr):
    # Some extra logic to make an error message useful.
    if check_stdout and check_stderr:
      return 'stdout or stderr'
    elif check_stdout:
      return 'stdout'
    elif check_stderr:
      return 'stderr'

  def _AssertOutputEndsInMsg(self, check_msg_func,
                             check_stdout, check_stderr):
    """Pass if requested output(s) ends(end) with an error message."""
    assert check_stdout or check_stderr

    lines = []
    if check_stdout:
      stdout_lines = self._GetOutputCapt().GetStdoutLines(include_empties=False)
      if stdout_lines:
        lines.append(stdout_lines[-1])
    if check_stderr:
      stderr_lines = self._GetOutputCapt().GetStderrLines(include_empties=False)
      if stderr_lines:
        lines.append(stderr_lines[-1])

    result = self._ContainsMsgLine(lines, check_msg_func)

    # Some extra logic to make an error message useful.
    output_desc = self._GenOutputDescription(check_stdout, check_stderr)

    msg = ('expected %s to end with %s,\nbut did not find it in:\n%s' %
           (output_desc, check_msg_func.description, lines))
    self.assertTrue(result, msg=msg)

  def FuncCatchSystemExit(self, func, *args, **kwargs):
    """Run |func| with |args| and |kwargs| and catch SystemExit.

    Return tuple (return value or None, SystemExit number code or None).
    """
    try:
      returnval = func(*args, **kwargs)
      return returnval, None
    except SystemExit as ex:
      exit_code = ex.args[0]
      return None, exit_code


class RunCommandErrorStrTest(unittest.TestCase):
  """Test the RunCommandError."""

  def testNonUTF8Characters(self):
    """Test that non-UTF8 characters do not kill __str__."""
    result = cmd_util.run(['ls', '/does/not/exist'], check=False)
    rce = cmd_util.RunCommandError('\x81', result)
    str(rce)


class CmdToStrTest(unittest.TestCase):
  """Test the CmdToStr function."""

  def _assertEqual(self, func, test_input, test_output, result):
    """Like assertEqual but with built in diff support."""
    msg = ('Expected %s to translate %r to %r, but got %r' %
           (func, test_input, test_output, result))
    self.assertEqual(test_output, result, msg)

  def _testData(self, functor, tests, check_type=True):
    """Process an iterable of test data."""
    for test_output, test_input in tests:
      result = functor(test_input)
      self._assertEqual(functor.__name__, test_input, test_output, result)

      if check_type:
        # Also make sure the result is a string, otherwise the %r output will
        # include a "u" prefix and that is not good for logging.
        self.assertEqual(type(test_output), str)

  def testShellQuote(self):
    """Basic ShellQuote tests."""
    # Tuples of (expected output string, input data).
    tests_quote = (
        ("''", ''),
        ('a', u'a'),
        ("'a b c'", u'a b c'),
        ("'a\tb'", 'a\tb'),
        ("'/a$file'", '/a$file'),
        ("'/a#file'", '/a#file'),
        ("""'b"c'""", 'b"c'),
        ("'a@()b'", 'a@()b'),
        ('j%k', 'j%k'),
        # pylint: disable=invalid-triple-quote
        # https://github.com/edaniszewski/pylint-quotes/issues/20
        (r'''"s'a\$va\\rs"''', r"s'a$va\rs"),
        (r'''"\\'\\\""''', r'''\'\"'''),
        (r'''"'\\\$"''', r"""'\$"""),
    )

    bytes_quote = (
        # Since we allow passing bytes down, quote them too.
        ('bytes', b'bytes'),
        ("'by tes'", b'by tes'),
        ('bytes', u'bytes'),
        ("'by tes'", u'by tes'),
    )

    # Expected input output specific to ShellUnquote. This string cannot be
    # produced by ShellQuote but is still a valid bash escaped string.
    self._testData(cmd_util.ShellQuote, bytes_quote)
    self._testData(cmd_util.ShellQuote, tests_quote)

  def testShellQuoteOjbects(self):
    """Test objects passed to ShellQuote."""
    self.assertEqual('None', cmd_util.ShellQuote(None))
    self.assertNotEqual('', cmd_util.ShellQuote(object))

  def testCmdToStr(self):
    """Test dict of expected output strings to input lists."""
    tests = (
        (r'a b', ['a', 'b']),
        (r"'a b' c", ['a b', 'c']),
        # pylint: disable=invalid-triple-quote
        # https://github.com/edaniszewski/pylint-quotes/issues/20
        (r'''a "b'c"''', ['a', "b'c"]),
        (r'''a "/'\$b" 'a b c' "xy'z"''',
         [u'a', "/'$b", 'a b c', "xy'z"]),
        ('', []),
        ('a b c', [b'a', 'b', u'c']),
        ('bad None cmd', ['bad', None, 'cmd']),
    )
    self._testData(cmd_util.CmdToStr, tests)


class TestRunCommandNoMock(unittest.TestCase):
  """Class that tests run by not mocking subprocess.Popen."""

  def testErrorCodeNotRaisesError(self):
    """Don't raise exception when command returns non-zero exit code."""
    result = cmd_util.run(['ls', '/does/not/exist'], check=False)
    self.assertTrue(result.returncode != 0)

  def testMissingCommandRaisesError(self):
    """Raise error when command is not found."""
    self.assertRaises(cmd_util.RunCommandError, cmd_util.run,
                      ['/does/not/exist'], check=True)
    self.assertRaises(cmd_util.RunCommandError, cmd_util.run,
                      ['/does/not/exist'], check=False)

  def testDryRun(self):
    """Verify dryrun doesn't run the real command."""
    # Check exit & output when not captured.
    result = cmd_util.run(['false'], dryrun=True)
    self.assertEqual(0, result.returncode)
    self.assertEqual(None, result.stdout)
    self.assertEqual(None, result.stderr)

    # Check captured binary output.
    result = cmd_util.run(['echo', 'hi'], dryrun=True,
                          capture_output=True)
    self.assertEqual(0, result.returncode)
    self.assertEqual(b'', result.stdout)
    self.assertEqual(b'', result.stderr)

    # Check captured text output.
    result = cmd_util.run(['echo', 'hi'], dryrun=True,
                          capture_output=True, encoding='utf-8')
    self.assertEqual(0, result.returncode)
    self.assertEqual('', result.stdout)
    self.assertEqual('', result.stderr)

    # Check captured merged output.
    result = cmd_util.run(['echo', 'hi'], dryrun=True,
                          stdout=True, stderr=subprocess.STDOUT)
    self.assertEqual(0, result.returncode)
    self.assertEqual(b'', result.stdout)
    self.assertEqual(None, result.stderr)

  def testInputBytes(self):
    """Verify input argument when it is bytes."""
    for data in (b'', b'foo', b'bar\nhigh'):
      result = cmd_util.run(['cat'], input=data, capture_output=True)
      self.assertEqual(result.stdout, data)

  def testInputBytesEncoding(self):
    """Verify bytes input argument when encoding is set."""
    for data in (b'', b'foo', b'bar\nhigh'):
      result = cmd_util.run(['cat'], input=data, encoding='utf-8',
                            capture_output=True)
      self.assertEqual(result.stdout, data.decode('utf-8'))

  def testInputString(self):
    """Verify input argument when it is a string."""
    for data in ('', 'foo', 'bar\nhigh'):
      result = cmd_util.run(['cat'], input=data, capture_output=True)
      self.assertEqual(result.stdout, data.encode('utf-8'))

  def testInputStringEncoding(self):
    """Verify bytes input argument when encoding is set."""
    for data in ('', 'foo', 'bar\nhigh'):
      result = cmd_util.run(['cat'], input=data, encoding='utf-8',
                            capture_output=True)
      self.assertEqual(result.stdout, data)

  def testInputFileObject(self):
    """Verify input argument when it is a file object."""
    with open('/dev/null') as wf:
      result = cmd_util.run(['cat'], input=wf,
                            capture_output=True)
      self.assertEqual(result.output, b'')

      with open(__file__) as f:
        result = cmd_util.run(['cat'], input=f, capture_output=True)
        self.assertEqual(result.stdout,
                         ReadFile(__file__, mode='rb'))

  def testInputFileDescriptor(self):
    """Verify input argument when it is a file descriptor."""
    with open('/dev/null') as f:
      result = cmd_util.run(['cat'], input=f.fileno(),
                            capture_output=True)
      self.assertEqual(result.output, b'')

    with open(__file__) as f:
      result = cmd_util.run(['cat'], input=f.fileno(),
                            capture_output=True)
      self.assertEqual(result.stdout,
                       ReadFile(__file__, mode='rb'))

  def testMixedEncodingCommand(self):
    """Verify cmd can mix bytes & strings."""
    result = cmd_util.run([b'echo', 'hi', u'ß'], capture_output=True,
                          encoding='utf-8')
    self.assertEqual(result.stdout, u'hi ß\n')

  def testEncodingBinaryOutput(self):
    """Verify encoding=None output handling."""
    result = cmd_util.run(b'echo o\xff ut; echo e\xff rr >&2',
                          shell=True, capture_output=True)
    self.assertEqual(result.stdout, b'o\xff ut\n')
    self.assertEqual(result.stderr, b'e\xff rr\n')

  def testEncodingUtf8Output(self):
    """Verify encoding='utf-8' output handling."""
    result = cmd_util.run(['echo', u'ß'], capture_output=True,
                          encoding='utf-8')
    self.assertEqual(result.stdout, u'ß\n')

  def testEncodingStrictInvalidUtf8Output(self):
    """Verify encoding='utf-8' output with invalid content."""
    with self.assertRaises(UnicodeDecodeError):
      cmd_util.run(['echo', b'\xff'], capture_output=True,
                   encoding='utf-8')
    with self.assertRaises(UnicodeDecodeError):
      cmd_util.run(['echo', b'\xff'], capture_output=True,
                   encoding='utf-8', errors='strict')

  def testEncodingReplaceInvalidUtf8Output(self):
    """Verify encoding='utf-8' errors='replace' output with invalid content."""
    result = cmd_util.run(['echo', b'S\xffE'], capture_output=True,
                          encoding='utf-8', errors='replace')
    self.assertEqual(result.stdout, u'S\ufffdE\n')


def _ForceLoggingLevel(functor):
  def inner(*args, **kwargs):
    logger = logging.getLogger()
    current = logger.getEffectiveLevel()
    try:
      logger.setLevel(logging.INFO)
      return functor(*args, **kwargs)
    finally:
      logger.setLevel(current)
  return inner


class TestRunCommandOutput(TempDirTestCase, OutputTestCase):
  """Tests of run output options."""

  @_ForceLoggingLevel
  def testLogStdoutToFile(self):
    log = os.path.join(self.tempdir, 'output')
    ret = cmd_util.run(['echo', 'monkeys'], stdout=log)
    self.assertEqual(ReadFile(log), 'monkeys\n')
    self.assertIs(ret.output, None)
    self.assertIs(ret.error, None)

    os.unlink(log)
    ret = cmd_util.run(
        ['sh', '-c', 'echo monkeys3 >&2'],
        stdout=log, stderr=True)
    self.assertEqual(ret.error, b'monkeys3\n')
    self.assertEqual(os.path.getsize(log), 0)

    os.unlink(log)
    ret = cmd_util.run(
        ['sh', '-c', 'echo monkeys4; echo monkeys5 >&2'],
        stdout=log, stderr=subprocess.STDOUT)
    self.assertIs(ret.output, None)
    self.assertIs(ret.error, None)
    self.assertEqual(ReadFile(log), 'monkeys4\nmonkeys5\n')


  @_ForceLoggingLevel
  def testLogStdoutToFileWithOrWithoutAppend(self):
    log = os.path.join(self.tempdir, 'output')
    ret = cmd_util.run(['echo', 'monkeys'], stdout=log)
    self.assertEqual(ReadFile(log), 'monkeys\n')
    self.assertIs(ret.output, None)
    self.assertIs(ret.error, None)

    # Without append
    ret = cmd_util.run(['echo', 'monkeys2'], stdout=log)
    self.assertEqual(ReadFile(log), 'monkeys2\n')
    self.assertIs(ret.output, None)
    self.assertIs(ret.error, None)

    # With append
    ret = cmd_util.run(
        ['echo', 'monkeys3'], append_to_file=True, stdout=log)
    self.assertEqual(ReadFile(log), 'monkeys2\nmonkeys3\n')
    self.assertIs(ret.output, None)
    self.assertIs(ret.error, None)

  def testOutputFileHandle(self):
    """Verify writing to existing file handles."""
    stdout = os.path.join(self.tempdir, 'stdout')
    stderr = os.path.join(self.tempdir, 'stderr')
    with open(stdout, 'wb') as outfp:
      with open(stderr, 'wb') as errfp:
        cmd_util.run(['sh', '-c', 'echo out; echo err >&2'],
                           stdout=outfp, stderr=errfp)
    self.assertEqual('out\n', ReadFile(stdout))
    self.assertEqual('err\n', ReadFile(stderr))

  def testRunCommandRedirectStdoutStderrOnCommandError(self):
    """Tests that stderr is captured when run raises."""
    with self.assertRaises(cmd_util.RunCommandError) as cm:
      cmd_util.run(['cat', '/'], stderr=True)
    self.assertIsNotNone(cm.exception.result.error)
    self.assertNotEqual('', cm.exception.result.error)

  def _CaptureLogOutput(self, cmd, **kwargs):
    """Capture logging output of run."""
    log = os.path.join(self.tempdir, 'output')
    fh = logging.FileHandler(log)
    fh.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(fh)
    cmd_util.run(cmd, **kwargs)
    logging.getLogger().removeHandler(fh)
    output = ReadFile(log)
    fh.close()
    return output

  @_ForceLoggingLevel
  def testLogOutput(self):
    """Normal log_output, stdout followed by stderr."""
    cmd = 'echo Greece; echo Italy >&2; echo Spain'
    log_output = ('run: /bin/bash -c '
                  "'echo Greece; echo Italy >&2; echo Spain'\n"
                  '(stdout):\nGreece\nSpain\n\n(stderr):\nItaly\n\n')
    output = self._CaptureLogOutput(cmd, shell=True, log_output=True,
                                    encoding='utf-8')
    self.assertEqual(output, log_output)


class TarballTests(TempDirTestCase):
  """Test tarball handling functions."""

  def setUp(self):
    """Create files/dirs needed for tar test."""
    TempDirTestCase.setUp(self)
    self.tarball_path = os.path.join(self.tempdir, 'test.tar.xz')
    self.inputDir = os.path.join(self.tempdir, 'inputs')
    self.inputs = [
        'inputA',
        'inputB',
        'sub/subfile',
        'sub2/subfile',
    ]

    self.inputsWithDirs = [
        'inputA',
        'inputB',
        'sub',
        'sub2',
    ]


    # Create the input files.
    for i in self.inputs:
      WriteFile(os.path.join(self.inputDir, i), i, makedirs=True)

  def testCreateSuccess(self):
    """Create a tarfile."""
    cmd_util.CreateTarball(self.tarball_path, self.inputDir,
                                 inputs=self.inputs)

  def testCreateSuccessWithDirs(self):
    """Create a tarfile."""
    cmd_util.CreateTarball(self.tarball_path, self.inputDir,
                                 inputs=self.inputsWithDirs)

  def testCreateSuccessWithTooManyFiles(self):
    """Test a tarfile creation with -T /dev/stdin."""
    # pylint: disable=protected-access
    num_inputs = cmd_util._THRESHOLD_TO_USE_T_FOR_TAR + 1
    inputs = ['input%s' % x for x in range(num_inputs)]
    largeInputDir = os.path.join(self.tempdir, 'largeinputs')
    for i in inputs:
      WriteFile(os.path.join(largeInputDir, i), i, makedirs=True)
    cmd_util.CreateTarball(
        self.tarball_path, largeInputDir, inputs=inputs)


class MockTestCase(unittest.TestCase):
  """Python-mock based test case; compatible with StackedSetup."""

  def setUp(self):
    self._patchers = []

  def StartPatcher(self, patcher):
    """Call start() on the patcher, and stop() in tearDown."""
    m = patcher.start()
    self._patchers.append(patcher)
    self.addCleanup(patcher)
    return m

  def PatchObject(self, *args, **kwargs):
    """Create and start a mock.patch.object().

    stop() will be called automatically during tearDown.
    """
    return self.StartPatcher(mock.patch.object(*args, **kwargs))

  def PatchDict(self, *args, **kwargs):
    """Create and start a mock.patch.dict().

    stop() will be called automatically during tearDown.
    """
    return self.StartPatcher(mock.patch.dict(*args, **kwargs))


class FailedCreateTarballTests(unittest.TestCase):
  """Tests special case error handling for CreateTarball."""

  def setUp(self):
    """Mock run mock."""
    # Each test can change this value as needed.  Each element is the return
    # code in the CommandResult for subsequent calls to run().
    MockTestCase.setUp(self)
    self.tarResults = []

    def Result(*_args, **_kwargs):
      """Create CommandResult objects for each tarResults value in turn."""
      return cmd_util.CommandResult(returncode=self.tarResults.pop(0))

    patcher = mock.patch.object(cmd_util, 'run', side_effect=Result)

    self.mockRun = patcher.start()
    self.addCleanup(patcher.stop)

  def testSuccess(self):
    """CreateTarball works the first time."""
    self.tarResults = [0]
    cmd_util.CreateTarball('foo', 'bar', inputs=['a', 'b'])

    self.assertEqual(self.mockRun.call_count, 1)

  def testFailedOnceSoft(self):
    """Force a single retry for CreateTarball."""
    self.tarResults = [1, 0]
    cmd_util.CreateTarball('foo', 'bar', inputs=['a', 'b'], timeout=0)

    self.assertEqual(self.mockRun.call_count, 2)

  def testFailedOnceHard(self):
    """Test unrecoverable error."""
    self.tarResults = [2]
    with self.assertRaises(cmd_util.RunCommandError) as cm:
      cmd_util.CreateTarball('foo', 'bar', inputs=['a', 'b'])

    self.assertEqual(self.mockRun.call_count, 1)
    self.assertEqual(cm.exception.args[1].returncode, 2)

  def testFailedThriceSoft(self):
    """Exhaust retries for recoverable errors."""
    self.tarResults = [1, 1, 1]
    with self.assertRaises(cmd_util.RunCommandError) as cm:
      cmd_util.CreateTarball('foo', 'bar', inputs=['a', 'b'], timeout=0)

    self.assertEqual(self.mockRun.call_count, 3)
    self.assertEqual(cm.exception.args[1].returncode, 1)


if __name__ == "__main__":
  unittest.main()
