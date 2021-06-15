# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Taring/cmd utilities to support container_util."""

import contextlib
import errno
import functools
import operator
import os
import signal
import subprocess
import sys
import tempfile
import time
import logging


from . import signals


# For use by ShellQuote.  Match all characters that the shell might treat
# specially.  This means a number of things:
#  - Reserved characters.
#  - Characters used in expansions (brace, variable, path, globs, etc...).
#  - Characters that an interactive shell might use (like !).
#  - Whitespace so that one arg turns into multiple.
# See the bash man page as well as the POSIX shell documentation for more info:
#   http://www.gnu.org/software/bash/manual/bashref.html
#   http://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html
_SHELL_QUOTABLE_CHARS = frozenset('[|&;()<> \t!{}[]=*?~$"\'\\#^')
# The chars that, when used inside of double quotes, need escaping.
# Order here matters as we need to escape backslashes first.
_SHELL_ESCAPE_CHARS = r'\"`$'

# The number of files is larger than this, we will use -T option
# and files to be added may not show up to the command line.
_THRESHOLD_TO_USE_T_FOR_TAR = 50


def ShellQuote(s):
  """Quote |s| in a way that is safe for use in a shell.

  We aim to be safe, but also to produce "nice" output.  That means we don't
  use quotes when we don't need to, and we prefer to use less quotes (like
  putting it all in single quotes) than more (using double quotes and escaping
  a bunch of stuff, or mixing the quotes).

  While python does provide a number of alternatives like:
   - pipes.quote
   - shlex.quote
  They suffer from various problems like:
   - Not widely available in different python versions.
   - Do not produce pretty output in many cases.
   - Are in modules that rarely otherwise get used.

  Note: We don't handle reserved shell words like "for" or "case".  This is
  because those only matter when they're the first element in a command, and
  there is no use case for that.  When we want to run commands, we tend to
  run real programs and not shell ones.

  Args:
    s: The string to quote.

  Returns:
    A safely (possibly quoted) string.
  """
  if sys.version_info.major < 3:
    # This is a bit of a hack.  Python 2 will display strings with u prefixes
    # when logging which makes things harder to work with.  Writing bytes to
    # stdout will be interpreted as UTF-8 content implicitly.
    if isinstance(s, str):
      try:
        s = s.encode('utf-8')
      except UnicodeDecodeError:
        # We tried our best.  Let Python's automatic mixed encoding kick in.
        pass
    else:
      return repr(s)
  else:
    # If callers pass down bad types, don't blow up.
    if isinstance(s, bytes):
      s = s.decode('utf-8', 'backslashreplace')
    elif not isinstance(s, str):
      return repr(s)

  # See if no quoting is needed so we can return the string as-is.
  for c in s:
    if c in _SHELL_QUOTABLE_CHARS:
      break
  else:
    if not s:
      return "''"
    else:
      return s

  # See if we can use single quotes first.  Output is nicer.
  if "'" not in s:
    return "'%s'" % s

  # Have to use double quotes.  Escape the few chars that still expand when
  # used inside of double quotes.
  for c in _SHELL_ESCAPE_CHARS:
    if c in s:
      s = s.replace(c, r'\%s' % c)
  return '"%s"' % s


def CmdToStr(cmd):
  """Translate a command list into a space-separated string.

  The resulting string should be suitable for logging messages and for
  pasting into a terminal to run.  Command arguments are surrounded by
  quotes to keep them grouped, even if an argument has spaces in it.

  Examples:
    ['a', 'b'] ==> "'a' 'b'"
    ['a b', 'c'] ==> "'a b' 'c'"
    ['a', 'b\'c'] ==> '\'a\' "b\'c"'
    [u'a', "/'$b"] ==> '\'a\' "/\'$b"'
    [] ==> ''
    See unittest for additional (tested) examples.

  Args:
    cmd: List of command arguments.

  Returns:
    String representing full command.
  """
  # If callers pass down bad types, triage it a bit.
  if isinstance(cmd, (list, tuple)):
    return ' '.join(ShellQuote(arg) for arg in cmd)
  else:
    raise ValueError('cmd must be list or tuple, not %s: %r' %
                     (type(cmd), repr(cmd)))


class CompletedProcess(getattr(subprocess, 'CompletedProcess', object)):
  """An object to store various attributes of a child process.

  This is akin to subprocess.CompletedProcess.
  """

  # The linter is confused by the getattr usage above.
  # TODO(vapier): Drop this once we're Python 3-only and we drop getattr.
  # pylint: disable=bad-option-value,super-on-old-class
  def __init__(self, args=None, returncode=None, stdout=None, stderr=None):
    if sys.version_info.major < 3:
      self.args = args
      self.stdout = stdout
      self.stderr = stderr
      self.returncode = returncode
    else:
      super(CompletedProcess, self).__init__(
          args=args, returncode=returncode, stdout=stdout, stderr=stderr)

  @property
  def cmd(self):
    """Alias to self.args to better match other subprocess APIs."""
    return self.args

  @property
  def cmdstr(self):
    """Return self.cmd as a well shell-quoted string useful for log messages."""
    if self.args is None:
      return ''
    else:
      return CmdToStr(self.args)

  def check_returncode(self):
    """Raise CalledProcessError if the exit code is non-zero."""
    if self.returncode:
      raise CalledProcessError(
          returncode=self.returncode, cmd=self.args, stdout=self.stdout,
          stderr=self.stderr, msg='check_returncode failed')


# TODO(crbug.com/1006587): Migrate users to CompletedProcess and drop this.
class CommandResult(CompletedProcess):
  """An object to store various attributes of a child process.

  This is akin to subprocess.CompletedProcess.
  """

  # The linter is confused by the getattr usage above.
  # TODO(vapier): Drop this once we're Python 3-only and we drop getattr.
  # pylint: disable=bad-option-value,super-on-old-class
  def __init__(self, cmd=None, error=None, output=None, returncode=None,
               args=None, stdout=None, stderr=None):
    if args is None:
      args = cmd
    elif cmd is not None:
      raise TypeError('Only specify |args|, not |cmd|')
    if stdout is None:
      stdout = output
    elif output is not None:
      raise TypeError('Only specify |stdout|, not |output|')
    if stderr is None:
      stderr = error
    elif error is not None:
      raise TypeError('Only specify |stderr|, not |error|')

    super(CommandResult, self).__init__(args=args, stdout=stdout, stderr=stderr,
                                        returncode=returncode)

  @property
  def output(self):
    """Backwards compat API."""
    return self.stdout

  @property
  def error(self):
    """Backwards compat API."""
    return self.stderr


class CalledProcessError(subprocess.CalledProcessError):
  """Error caught in run() function.

  This is akin to subprocess.CalledProcessError.  We do not support |output|,
  only |stdout|.

  Attributes:
    returncode: The exit code of the process.
    cmd: The command that triggered this exception.
    msg: Short explanation of the error.
    exception: The underlying Exception if available.
  """

  def __init__(self, returncode, cmd, stdout=None, stderr=None, msg=None,
               exception=None):
    if exception is not None and not isinstance(exception, Exception):
      raise TypeError('exception must be an exception instance; got %r'
                      % (exception,))

    super(CalledProcessError, self).__init__(returncode, cmd, stdout)
    # The parent class will set |output|, so delete it.
    del self.output
    # TODO(vapier): When we're Python 3-only, delete this assignment as the
    # parent handles it for us.
    self.stdout = stdout
    # TODO(vapier): When we're Python 3-only, move stderr to the init above.
    self.stderr = stderr
    self.msg = msg
    self.exception = exception

  @property
  def cmdstr(self):
    """Return self.cmd as a well shell-quoted string useful for log messages."""
    if self.cmd is None:
      return ''
    else:
      return CmdToStr(self.cmd)

  def Stringify(self, stdout=True, stderr=True):
    """Custom method for controlling what is included in stringifying this.

    Args:
      stdout: Whether to include captured stdout in the return value.
      stderr: Whether to include captured stderr in the return value.

    Returns:
      A summary string for this result.
    """
    items = [
        u'return code: %s; command: %s' % (
            self.returncode, self.cmdstr),
    ]
    if stderr and self.stderr:
      stderr = self.stderr
      if isinstance(stderr, bytes):
        stderr = stderr.decode('utf-8', 'replace')
      items.append(stderr)
    if stdout and self.stdout:
      stdout = self.stdout
      if isinstance(stdout, bytes):
        stdout = stdout.decode('utf-8', 'replace')
      items.append(stdout)
    if self.msg:
      msg = self.msg
      if isinstance(msg, bytes):
        msg = msg.decode('utf-8', 'replace')
      items.append(msg)
    return u'\n'.join(items)

  def __str__(self):
    if sys.version_info.major < 3:
      # __str__ needs to return ascii, thus force a conversion to be safe.
      return self.Stringify().encode('ascii', 'xmlcharrefreplace')
    else:
      return self.Stringify()

  def __eq__(self, other):
    return (isinstance(other, type(self)) and
            self.returncode == other.returncode and
            self.cmd == other.cmd and
            self.stdout == other.stdout and
            self.stderr == other.stderr and
            self.msg == other.msg and
            self.exception == other.exception)

  def __ne__(self, other):
    return not self.__eq__(other)


# TODO(crbug.com/1006587): Migrate users to CompletedProcess and drop this.
class RunCommandError(CalledProcessError):
  """Error caught in run() method.

  Attributes:
    args: Tuple of the attributes below.
    msg: Short explanation of the error.
    result: The CommandResult that triggered this error, if available.
    exception: The underlying Exception if available.
  """

  def __init__(self, msg, result=None, exception=None):
    # This makes mocking tests easier.
    if result is None:
      result = CommandResult()
    elif not isinstance(result, CommandResult):
      raise TypeError('result must be a CommandResult instance; got %r'
                      % (result,))

    self.args = (msg, result, exception)
    self.result = result
    super(RunCommandError, self).__init__(
        returncode=result.returncode, cmd=result.args, stdout=result.stdout,
        stderr=result.stderr, msg=msg, exception=exception)


class TerminateRunCommandError(RunCommandError):
  """We were signaled to shutdown while running a command.

  Client code shouldn't generally know, nor care about this class.  It's
  used internally to suppress retry attempts when we're signaled to die.
  """

def _KillChildProcess(proc, int_timeout, kill_timeout, cmd, original_handler,
                      signum, frame):
  """Used as a signal handler by run.

  This is internal to run.  No other code should use this.
  """
  if signum:
    # If we've been invoked because of a signal, ignore delivery of that signal
    # from this point forward.  The invoking context of _KillChildProcess
    # restores signal delivery to what it was prior; we suppress future delivery
    # till then since this code handles SIGINT/SIGTERM fully including
    # delivering the signal to the original handler on the way out.
    signal.signal(signum, signal.SIG_IGN)

  # Do not trust Popen's returncode alone; we can be invoked from contexts where
  # the Popen instance was created, but no process was generated.
  if proc.returncode is None and proc.pid is not None:
    try:
      while proc.poll_lock_breaker() is None and int_timeout >= 0:
        time.sleep(0.1)
        int_timeout -= 0.1

      proc.terminate()
      while proc.poll_lock_breaker() is None and kill_timeout >= 0:
        time.sleep(0.1)
        kill_timeout -= 0.1

      if proc.poll_lock_breaker() is None:
        # Still doesn't want to die.  Too bad, so sad, time to die.
        proc.kill()
    except EnvironmentError as e:
      logging.warning('Ignoring unhandled exception in _KillChildProcess: %s',
                      e)

    # Ensure our child process has been reaped.
    kwargs = {}
    if sys.version_info.major >= 3:
      # ... but don't wait forever.
      kwargs['timeout'] = 60
    proc.wait_lock_breaker(**kwargs)

  if not signals.RelaySignal(original_handler, signum, frame):
    # Mock up our own, matching exit code for signaling.
    cmd_result = CommandResult(args=cmd, returncode=signum << 8)
    raise TerminateRunCommandError('Received signal %i' % signum, cmd_result)


class _Popen(subprocess.Popen):
  """subprocess.Popen derivative customized for our usage.

  Specifically, we fix terminate/send_signal/kill to work if the child process
  was a setuid binary; on vanilla kernels, the parent can wax the child
  regardless, on goobuntu this apparently isn't allowed, thus we fall back
  to the sudo machinery we have.

  While we're overriding send_signal, we also suppress ESRCH being raised
  if the process has exited, and suppress signaling all together if the process
  has knowingly been waitpid'd already.
  """

  # Pylint seems to be buggy with the send_signal signature detection.
  # pylint: disable=arguments-differ
  def send_signal(self, sig):
    if self.returncode is not None:
      # The original implementation in Popen would allow signaling whatever
      # process now occupies this pid, even if the Popen object had waitpid'd.
      # Since we can escalate to sudo kill, we do not want to allow that.
      # Fixing this addresses that angle, and makes the API less sucky in the
      # process.
      return

    try:
      os.kill(self.pid, sig)
    except EnvironmentError as e:
      if e.errno == errno.EPERM:
        # Kill returns either 0 (signal delivered), or 1 (signal wasn't
        # delivered).  This isn't particularly informative, but we still
        # need that info to decide what to do, thus the check=False.
        ret = sudo_run(['kill', '-%i' % sig, str(self.pid)],
                       print_cmd=False, stdout=True,
                       stderr=True, check=False)
        if ret.returncode == 1:
          # The kill binary doesn't distinguish between permission denied,
          # and the pid is missing.  Denied can only occur under weird
          # grsec/selinux policies.  We ignore that potential and just
          # assume the pid was already dead and try to reap it.
          self.poll()
      elif e.errno == errno.ESRCH:
        # Since we know the process is dead, reap it now.
        # Normally Popen would throw this error- we suppress it since frankly
        # that's a misfeature and we're already overriding this method.
        self.poll()
      else:
        raise

  def _lock_breaker(self, func, *args, **kwargs):
    """Helper to manage the waitpid lock.

    Workaround https://bugs.python.org/issue25960.
    """
    # If the lock doesn't exist, or is not locked, call the func directly.
    lock = getattr(self, '_waitpid_lock', None)
    if lock is not None and lock.locked():
      try:
        lock.release()
        return func(*args, **kwargs)
      finally:
        if not lock.locked():
          lock.acquire()
    else:
      return func(*args, **kwargs)

  def poll_lock_breaker(self, *args, **kwargs):
    """Wrapper around poll() to break locks if needed."""
    return self._lock_breaker(self.poll, *args, **kwargs)

  def wait_lock_breaker(self, *args, **kwargs):
    """Wrapper around wait() to break locks if needed."""
    return self._lock_breaker(self.wait, *args, **kwargs)


# pylint: disable=redefined-builtin
def run(cmd, print_cmd=True, stdout=None, stderr=None,
        cwd=None, input=None,
        shell=False, env=None, extra_env=None, ignore_sigint=False,
        chroot_args=None, debug_level=logging.INFO,
        check=True, int_timeout=1, kill_timeout=1,
        log_output=False, capture_output=False,
        quiet=False, encoding=None, errors=None, dryrun=False,
        **kwargs):
  """Runs a command.

  Args:
    cmd: cmd to run.  Should be input to subprocess.Popen. If a string, shell
      must be true. Otherwise the command must be an array of arguments, and
      shell must be false.
    print_cmd: prints the command before running it.
    stdout: Where to send stdout.  This may be many things to control
      redirection:
        * None is the default; the existing stdout is used.
        * An existing file object (must be opened with mode 'w' or 'wb').
        * A string to a file (will be truncated & opened automatically).
        * subprocess.PIPE to capture & return the output.
        * A boolean to indicate whether to capture the output.
          True will capture the output via a tempfile (good for large output).
        * An open file descriptor (as a positive integer).
    stderr: Where to send stderr.  See |stdout| for possible values.  This also
      may be subprocess.STDOUT to indicate stderr & stdout should be combined.
    cwd: the working directory to run this cmd.
    input: The data to pipe into this command through stdin.  If a file object
      or file descriptor, stdin will be connected directly to that.
    shell: Controls whether we add a shell as a command interpreter.  See cmd
      since it has to agree as to the type.
    env: If non-None, this is the environment for the new process.  If
      enter_chroot is true then this is the environment of the enter_chroot,
      most of which gets removed from the cmd run.
    extra_env: If set, this is added to the environment for the new process.
      In enter_chroot=True case, these are specified on the post-entry
      side, and so are often more useful.  This dictionary is not used to
      clear any entries though.
    ignore_sigint: If True, we'll ignore signal.SIGINT before calling the
      child.  This is the desired behavior if we know our child will handle
      Ctrl-C.  If we don't do this, I think we and the child will both get
      Ctrl-C at the same time, which means we'll forcefully kill the child.
    chroot_args: An array of arguments for the chroot environment wrapper.
    debug_level: The debug level of run's output.
    check: Whether to raise an exception when command returns a non-zero exit
      code, or return the CommandResult object containing the exit code.
      Note: will still raise an exception if the cmd file does not exist.
    int_timeout: If we're interrupted, how long (in seconds) should we give the
      invoked process to clean up before we send a SIGTERM.
    kill_timeout: If we're interrupted, how long (in seconds) should we give the
      invoked process to shutdown from a SIGTERM before we SIGKILL it.
    log_output: Log the command and its output automatically.
    capture_output: Set |stdout| and |stderr| to True.
    quiet: Set |print_cmd| to False, and |capture_output| to True.
    encoding: Encoding for stdin/stdout/stderr, otherwise bytes are used.  Most
      users want 'utf-8' here for string data.
    errors: How to handle errors when |encoding| is used.  Defaults to 'strict',
      but 'ignore' and 'replace' are common settings.
    dryrun: Only log the command,and return a stub result.

  Returns:
    A CommandResult object.

  Raises:
    RunCommandError: Raised on error.
  """
  # Hide this function in pytest tracebacks when a RunCommandError is raised,
  # as seeing the contents of this function when a command fails is not helpful.
  # https://docs.pytest.org/en/latest/example/simple.html#writing-well-integrated-assertion-helpers
  __tracebackhide__ = operator.methodcaller('errisinstance', RunCommandError)

  # Handle backwards compatible settings.
  if 'log_stdout_to_file' in kwargs:
    logging.warning('run: log_stdout_to_file=X is now stdout=X')
    log_stdout_to_file = kwargs.pop('log_stdout_to_file')
    if log_stdout_to_file is not None:
      stdout = log_stdout_to_file
  stdout_file_mode = 'w+b'
  if 'append_to_file' in kwargs:
    # TODO(vapier): Enable this warning once chromite & users migrate.
    # logging.warning('run: append_to_file is now part of stdout')
    if kwargs.pop('append_to_file'):
      stdout_file_mode = 'a+b'
  assert not kwargs, 'Unknown arguments to run: %s' % (list(kwargs),)

  if quiet:
    print_cmd = False
    capture_output = True

  if capture_output:
    # TODO(vapier): Enable this once we migrate all the legacy arguments above.
    # if stdout is not None or stderr is not None:
    #   raise ValueError('capture_output may not be used with stdout & stderr')
    # TODO(vapier): Drop this specialization once we're Python 3-only as we can
    # pass this argument down to Popen directly.
    if stdout is None:
      stdout = True
    if stderr is None:
      stderr = True

  if encoding is not None and errors is None:
    errors = 'strict'

  # Set default for variables.
  popen_stdout = None
  popen_stderr = None
  stdin = None
  cmd_result = CommandResult()

  # Force the timeout to float; in the process, if it's not convertible,
  # a self-explanatory exception will be thrown.
  kill_timeout = float(kill_timeout)

  def _get_tempfile():
    try:
      return UnbufferedTemporaryFile()
    except EnvironmentError as e:
      if e.errno != errno.ENOENT:
        raise
      # This can occur if we were pointed at a specific location for our
      # TMP, but that location has since been deleted.  Suppress that issue
      # in this particular case since our usage gurantees deletion,
      # and since this is primarily triggered during hard cgroups shutdown.
      return UnbufferedTemporaryFile(dir='/tmp')

  # Modify defaults based on parameters.
  # Note that tempfiles must be unbuffered else attempts to read
  # what a separate process did to that file can result in a bad
  # view of the file.
  log_stdout_to_file = False
  if isinstance(stdout, str):
    popen_stdout = open(stdout, stdout_file_mode)
    log_stdout_to_file = True
  elif hasattr(stdout, 'fileno'):
    popen_stdout = stdout
    log_stdout_to_file = True
  elif isinstance(stdout, bool):
    # This check must come before isinstance(int) because bool subclasses int.
    if stdout:
      popen_stdout = _get_tempfile()
  elif isinstance(stdout, int):
    popen_stdout = stdout
  elif log_output:
    popen_stdout = _get_tempfile()

  log_stderr_to_file = False
  if hasattr(stderr, 'fileno'):
    popen_stderr = stderr
    log_stderr_to_file = True
  elif isinstance(stderr, bool):
    # This check must come before isinstance(int) because bool subclasses int.
    if stderr:
      popen_stderr = _get_tempfile()
  elif isinstance(stderr, int):
    popen_stderr = stderr
  elif log_output:
    popen_stderr = _get_tempfile()

  # If subprocesses have direct access to stdout or stderr, they can bypass
  # our buffers, so we need to flush to ensure that output is not interleaved.
  if popen_stdout is None or popen_stderr is None:
    sys.stdout.flush()
    sys.stderr.flush()

  # If input is a string, we'll create a pipe and send it through that.
  # Otherwise we assume it's a file object that can be read from directly.
  if isinstance(input, (str, bytes)):
    stdin = subprocess.PIPE
    # Allow people to always pass in bytes or strings regardless of encoding.
    # Our Popen usage takes care of converting everything to bytes first.
    #
    # Linter can't see that we're using |input| as a var, not a builtin.
    # pylint: disable=input-builtin
    if encoding and isinstance(input, str):
      input = input.encode(encoding, errors)
    elif not encoding and isinstance(input, str):
      input = input.encode('utf-8')
  elif input is not None:
    stdin = input
    input = None

  # Sanity check the command.  This helps when RunCommand is deep in the call
  # chain, but the command itself was constructed along the way.
  if isinstance(cmd, (str, bytes)):
    if not shell:
      raise ValueError('Cannot run a string command without a shell')
    cmd = ['/bin/bash', '-c', cmd]
    shell = False
  elif shell:
    raise ValueError('Cannot run an array command with a shell')
  elif not cmd:
    raise ValueError('Missing command to run')
  elif not isinstance(cmd, (list, tuple)):
    raise TypeError('cmd must be list or tuple, not %s: %r' %
                    (type(cmd), repr(cmd)))
  elif not all(isinstance(x, (bytes, str)) for x in cmd):
    raise TypeError('All command elements must be bytes/strings: %r' % (cmd,))

  # If we are using enter_chroot we need to use enterchroot pass env through
  # to the final command.
  env = env.copy() if env is not None else os.environ.copy()
  # Looking at localized error messages may be unexpectedly dangerous, so we
  # set LC_MESSAGES=C to make sure the output of commands is safe to inspect.
  env['LC_MESSAGES'] = 'C'
  env.update(extra_env if extra_env else {})

  # Print out the command before running.
  if dryrun or print_cmd or log_output:
    log = ''
    if dryrun:
      log += '(dryrun) '
    log += 'run: %s' % (CmdToStr(cmd),)
    if cwd:
      log += ' in %s' % (cwd,)
    logging.log(debug_level, '%s', log)

  cmd_result.args = cmd

  # We want to still something in dryrun mode so we process all the options
  # and return appropriate values (e.g. output with correct encoding).
  popen_cmd = ['true'] if dryrun else cmd

  proc = None
  # Verify that the signals modules is actually usable, and won't segfault
  # upon invocation of getsignal.  See signals.SignalModuleUsable for the
  # details and upstream python bug.
  use_signals = False
  try:
    proc = _Popen(popen_cmd, cwd=cwd, stdin=stdin, stdout=popen_stdout,
                  stderr=popen_stderr, shell=False, env=env,
                  close_fds=True)

    if use_signals:
      if ignore_sigint:
        old_sigint = signal.signal(signal.SIGINT, signal.SIG_IGN)
      else:
        old_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT,
                      functools.partial(_KillChildProcess, proc, int_timeout,
                                        kill_timeout, cmd, old_sigint))

      old_sigterm = signal.getsignal(signal.SIGTERM)
      signal.signal(signal.SIGTERM,
                    functools.partial(_KillChildProcess, proc, int_timeout,
                                      kill_timeout, cmd, old_sigterm))

    try:
      (cmd_result.stdout, cmd_result.stderr) = proc.communicate(input)
    finally:
      if use_signals:
        signal.signal(signal.SIGINT, old_sigint)
        signal.signal(signal.SIGTERM, old_sigterm)

      if (popen_stdout and not isinstance(popen_stdout, int) and
          not log_stdout_to_file):
        popen_stdout.seek(0)
        cmd_result.stdout = popen_stdout.read()
        popen_stdout.close()
      elif log_stdout_to_file:
        popen_stdout.close()

      if (popen_stderr and not isinstance(popen_stderr, int) and
          not log_stderr_to_file):
        popen_stderr.seek(0)
        cmd_result.stderr = popen_stderr.read()
        popen_stderr.close()

    cmd_result.returncode = proc.returncode

    # The try/finally block is a bit hairy.  We normally want the logged
    # output to be what gets passed back up.  But if there's a decode error,
    # we don't want it to break logging entirely.  If the output had a lot of
    # newlines, always logging it as bytes wouldn't be human readable.
    try:
      if encoding:
        if cmd_result.stdout is not None:
          cmd_result.stdout = cmd_result.stdout.decode(encoding, errors)
        if cmd_result.stderr is not None:
          cmd_result.stderr = cmd_result.stderr.decode(encoding, errors)
    finally:
      if log_output:
        if cmd_result.stdout:
          logging.log(debug_level, '(stdout):\n%s', cmd_result.stdout)
        if cmd_result.stderr:
          logging.log(debug_level, '(stderr):\n%s', cmd_result.stderr)

    if check and proc.returncode:
      msg = 'cmd=%s' % cmd
      if cwd:
        msg += ', cwd=%s' % cwd
      if extra_env:
        msg += ', extra env=%s' % extra_env
      raise RunCommandError(msg, cmd_result)
  except OSError as e:
    estr = str(e)
    if e.errno == errno.EACCES:
      estr += '; does the program need `chmod a+x`?'
    raise RunCommandError(estr, CommandResult(args=cmd), exception=e)
  finally:
    if proc is not None:
      # Ensure the process is dead.
      _KillChildProcess(proc, int_timeout, kill_timeout, cmd, None, None, None)

  # We might capture stdout/stderr for internal reasons (like logging), but we
  # don't want to let it leak back out to the callers.  They only get output if
  # they explicitly requested it.
  if stdout is None:
    cmd_result.stdout = None
  if stderr is None:
    cmd_result.stderr = None

  return cmd_result
# pylint: enable=redefined-builtin


# Convenience run methods.

COMP_NONE = 0
COMP_GZIP = 1
COMP_BZIP2 = 2
COMP_XZ = 3


def FindCompressor(compression, chroot=None):
  """Locate a compressor utility program (possibly in a chroot).

  Since we compress/decompress a lot, make it easy to locate a
  suitable utility program in a variety of locations.  We favor
  the one in the chroot over /, and the parallel implementation
  over the single threaded one.

  Args:
    compression: The type of compression desired.
    chroot: Optional path to a chroot to search.

  Returns:
    Path to a compressor.

  Raises:
    ValueError: If compression is unknown.
  """
  if compression == COMP_GZIP:
    std = 'gzip'
    para = 'pigz'
  elif compression == COMP_BZIP2:
    std = 'bzip2'
    para = 'pbzip2'
  elif compression == COMP_NONE:
    return 'cat'
  else:
    raise ValueError('unknown compression %s', compression)

  roots = []
  if chroot:
    roots.append(chroot)
  roots.append('/')

  for prog in [para, std]:
    for root in roots:
      for subdir in ['', 'usr']:
        path = os.path.join(root, subdir, 'bin', prog)
        if os.path.exists(path):
          return path

  return std


class TarballError(RunCommandError):
  """Error while running tar.

  We may run tar multiple times because of "soft" errors.  The result is from
  the last run instance.
  """


def CreateTarball(
    tarball_path, cwd, compression=COMP_BZIP2, chroot=None,
    inputs=None, timeout=300, extra_args=None, **kwargs):
  """Create a tarball.  Executes 'tar' on the commandline.

  Args:
    tarball_path: The path of the tar file to generate. Can be file descriptor.
    cwd: The directory to run the tar command.
    sudo: Whether to run with "sudo".
    compression: The type of compression desired.  See the FindCompressor
      function for details.
    chroot: See FindCompressor().
    inputs: A list of files or directories to add to the tarball.  If unset,
      defaults to ".".
    timeout: The number of seconds to wait on soft failure.
    extra_args: A list of extra args to pass to "tar".
    kwargs: Any run options/overrides to use.

  Returns:
    The cmd_result object returned by the run invocation.

  Raises:
    TarballError: if the tar command failed, possibly after retry.
  """
  if inputs is None:
    inputs = ['.']

  if extra_args is None:
    extra_args = []
  kwargs.setdefault('debug_level', logging.INFO)

  # Use a separate compression program - this enables parallel compression
  # in some cases.
  # Using 'raw' hole detection instead of 'seek' isn't that much slower, but
  # will provide much better results when archiving large disk images that are
  # not fully sparse.
  comp = FindCompressor(compression, chroot=chroot)
  cmd = (['tar'] +
         extra_args +
         ['--sparse', '--hole-detection=raw',
          '--use-compress-program', comp, '-c'])

  rc_stdout = None
  if isinstance(tarball_path, int):
    cmd += ['--to-stdout']
    rc_stdout = tarball_path
  else:
    cmd += ['-f', tarball_path]

  if len(inputs) > _THRESHOLD_TO_USE_T_FOR_TAR:
    cmd += ['--null', '-T', '/dev/stdin']
    rc_input = b'\0'.join(x.encode('utf-8') for x in inputs)
  else:
    cmd += list(inputs)
    rc_input = None

  rc_func = run

  # If tar fails with status 1, retry twice. Once after timeout seconds and
  # again 2*timeout seconds after that.
  for try_count in range(3):
    try:
      result = rc_func(cmd, cwd=cwd, **dict(kwargs, check=False,
               input=rc_input, stdout=rc_stdout))
    except RunCommandError as rce:
      # There are cases where run never executes the command (cannot find tar,
      # cannot execute tar, such as when cwd does not exist). Although the run
      # command will show low-level problems, we also want to log the context
      # of what CreateTarball was trying to do.
      logging.error('CreateTarball unable to run tar for %s in %s. cmd={%s}',
                    tarball_path, cwd, cmd)
      raise rce
    if result.returncode == 0:
      return result
    if result.returncode != 1 or try_count > 1:
      # Since the build is abandoned at this point, we will take 5
      # entire minutes to track down the competing process.
      # Error will have the low-level tar command error, so log the context
      # of the tar command (tarball_path file, current working dir).
      logging.error('CreateTarball failed creating %s in %s. cmd={%s}',
                    tarball_path, cwd, cmd)
      raise TarballError('CreateTarball', result)

    assert result.returncode == 1
    time.sleep(timeout * (try_count + 1))
    logging.warning('CreateTarball: tar: source modification time changed '
                    '(see crbug.com/547055), retrying')




def UnbufferedTemporaryFile(**kwargs):
  """Handle buffering changes in tempfile.TemporaryFile."""
  assert 'bufsize' not in kwargs
  assert 'buffering' not in kwargs
  if sys.version_info.major < 3:
    kwargs['bufsize'] = 0
  else:
    kwargs['buffering'] = 0
  return tempfile.TemporaryFile(**kwargs)
