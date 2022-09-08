# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utils for CFT Services."""

import select
from subprocess import Popen, PIPE


def run(cmd, shell: bool = True, stream: bool = True, raiserr: bool = False):
  """Run the given cmd....

  OK this is a fun one. This is specifically design with gcloud build in mind.

  Ideally, this would live stream out the builder log too, but I am pretty
    sure there is something hacky going on with the stream from the gcloud
    build side, as evident by some logs going to stderr instead of stdout,
    and the fact when you call `gcloud build <args>` with subprocess the
    logs will not be readable from the pipe in real time, and often until
    the task finishes, no matter how much you play w/ buffers.

  Please trust me to get EVERYTHING needed out of gcloud build, this
  (or something similar) is needed. Specifically:
    - stdout AND stderr need to be streamed, as gcloud build outputs non-err
      msgs on stderr (such as the log location)
    - stderr has to be read first in the loop, because once build "starts",
      the stdout basically locks until completion. Reading stderr first
      allows output of the "logs avalible at <link>" so that the user can
      follow the build along if desired
    - a final read must be done to ensure none of the stdout (and maybe err)
      is left in the PIPEs, as the final messages is what contains the build
      SHA.

  I can't find/figure out a better reader impl than this. I am open for
    anyone to re-write this and do better, if they can guarantee
    not to break the builder, and ensure when a `gcloud build` runs, the
    "stderr: Logs are available at [...]" msg comes out before the long
    pause as the builder actually runs... AND we get the digest sha (see
    sha_from_cloudbuild_out)

  Thanks for coming to my ted talk.

  Args:
    cmd: the cmd to run (can be str or list for now.)
    shell: if the cmd is a shell cmd or not.
    stream: option to print stdout/err as its received*
      *note the story book above for exceptions to this.
    raiserr: option to raise err on cmd failure.

  Returns:
    stdout, stderr, exitcode from the process.
  """

  child = Popen(cmd, shell=shell, stdout=PIPE, stderr=PIPE)
  assert (child.stdout and child.stderr) is not None
  # This is the pretty close to a fully working dual-stream reader that is
  # robust against gloudbuild weirdness. There is still lag between stdout
  # and it being printed, but thats due to the weirdness of the output from
  # gcloud build, its the best we can do. This impl should not loose any data
  # just that the stdout is slightly delayedo n the BUILD steps. HOWEVER, the
  # link for the log comes out in realtime, so the user can watch that if they
  # are worried about the build hanging.

  if stream:
    def _hanlde_output(out, buffer, stream_type):
      # Buffer must be of mutable
      if out:
        cleaned = out.strip().decode()
        print(f'{stream_type}: {cleaned}')
        buffer.append(cleaned)

    stdout_buffer: list = []
    stderr_buffer: list = []

    while True:
      reads = [child.stdout.fileno(), child.stderr.fileno()]
      ret = select.select(reads, [], [])
      for fd in ret[0]:
        if fd == child.stdout.fileno():
          _hanlde_output(child.stdout.readline(), stdout_buffer, 'stdout')
        if fd == child.stderr.fileno():
          _hanlde_output(child.stderr.readline(), stderr_buffer, 'stderr')

      if child.poll() is not None:
        # final read is needed.
        for line in child.stdout.readlines():
          _hanlde_output(line, stdout_buffer, 'stdout')
        for line in child.stderr.readlines():
          _hanlde_output(line, stderr_buffer, 'stderr')
        break

    out = '\n'.join(stdout_buffer)
    err = '\n'.join(stderr_buffer)
    code = child.returncode
  # Even when streaming communicating is OK, just out,err will be empty,
  # but this garuntees the process finishes so we can get an accurate
  # exit code.

  else:
    out, err = child.communicate()  # type: ignore
    code = child.returncode
    out, err = out.strip().decode(), err.strip().decode()  # type: ignore

  if raiserr and code != 0:
    raise Exception(f'\nCmd Failed: {cmd}\nError: {err}\nStatus: {code}\n')

  return out, err, code


def getoutput(cmd, shell: bool = True, stream: bool = False, log=True):
  """Get the stdout from a command."""
  print(f'Running cmd: {cmd}')
  return run(cmd, shell, stream)[0]
