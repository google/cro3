#!/usr/bin/env python3

# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Docker Builder for CFT Services."""

import json
import os
import select
from subprocess import Popen, PIPE

CWD = os.path.dirname(os.path.abspath(__file__))
CHROOT_DEFAULT = os.path.join(CWD, '../../../../../../chroot')
REGISTRY_DEFAULT = 'us-docker.pkg.dev'
PROJECT_DEFAULT = 'cros-registry/test-services'


class GCloudBuildException(Exception):
  """Raised when gcloud build fails"""
  pass


# TODO: this needs to be a common helper.
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

  # TODO, there is some builtin lib that will split cmds in non-shell stuff.
  child = Popen(cmd, shell=shell, stdout=PIPE, stderr=PIPE)
  assert child.stdout is not None
  assert child.stderr is not None
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


def getoutput(cmd, shell: bool = True, stream: bool = False):
  """Get the stdout from a command."""
  return run(cmd, shell, stream)[0]


class DockerBuilder():
  """Class for building Docker container images, either cloud or local."""

  def __init__(self,
               service: str,
               dockerfile: str = '',
               chroot: str = '',
               tags: str = '',
               output: str = '',
               registry_name: str = '',
               cloud_project: str = ''):
    """Why does an init need a docstring.

    Args:
      service: the service to be built, eg cros-test
      dockerfile: the full path and name of the Dockerfile
      chroot: chroot dir
      tags: tags for naming the image
      output: file which to write the output data from the build
      registry_name: name of the docker registry
      cloud_project: project name of registry
    """
    self.service = service
    self.dockerfile = dockerfile
    self.build_context = os.path.dirname(self.dockerfile)
    self.chroot = chroot
    self.tags = tags
    self.output = output
    self.registry_name = registry_name
    self.cloud_project = cloud_project
    self.validate_args()
    self.ensure_gcloud_helpers()

  def validate_args(self):
    """Validate the given args."""
    if not self.service or not self.dockerfile:
      raise Exception('Docker file and Service name required.')

    # labels=( "$@" )

    if os.path.exists('/etc/cros_chroot_version'):
      raise Exception('Must be run outside chroot')

    if not self.chroot:
      self.chroot = CHROOT_DEFAULT
    print(f'Using {self.chroot} for chroot.')

    if not os.path.exists(self.chroot):
      raise Exception(f'Given chroot path does not exist: {self.chroot}')

    if not self.tags:
      self.tags = [f'local-{getoutput("whoami")}']
      print(f'Defaulting tag to {self.tags}')

    if not self.registry_name:
      self.registry_name = REGISTRY_DEFAULT
      print(f'No registry_name given, using default {self.registry_name}')

    if not self.cloud_project:
      self.cloud_project = PROJECT_DEFAULT
      print(f'No cloud_project given, using default {self.cloud_project}')

    print(f'Using Docker Registry: {self.registry_name} for'
          f' cloudproject {self.cloud_project}')

    # TODO, make this a flag
    self.cloud_build_project = 'cros-registry'

    self.image_name = self.service
    self.image_path = os.path.join(self.registry_name,
                                   self.cloud_project,
                                   self.image_name)

  def ensure_gcloud_helpers(self):
    """Ensure gcloud is setup and ready.

    First call sets up default GCR registries, second call sets up
    Artifact Registry registries.
    """
    getoutput('gcloud --quiet --verbosity=error auth configure-docker')
    getoutput('gcloud --quiet --verbosity=error auth configure-docker'
              ' us-docker.pkg.dev')

  def structure_gcloud_tags(self):
    """Translate self.tags cloudbuild "--substitutions=" args.

    Example:
      tags=["kevin-postsubmit.123333.211","2385838192918392"]
      translates to: __BUILD_TAG0=us-docker.pkg.dev/cros-registry/test-services/cros-test:kevin-postsubmit.123333.211","2385838192918392

    Returns:
      A string ofthe tags to be substituted into the cloudbuild.yaml
    """
    subs = ''
    for i, tag in enumerate(self.tags):
      subs = subs + f'__BUILD_TAG{i}={self.image_path}:{tag},'
    # strip last comma
    return subs[:-1]

  def auth_gcloud(self):
    """Auth the gcloud creds, and access token."""
    print('\n== Gcloud helper configuration')
    print(getoutput('docker-credential-gcloud list'))
    print('\n== User Authorization Scopes')
    token = getoutput('gcloud auth print-access-token')
    print(f'Token found: {token}')
    out = getoutput(f'curl -H "Authorization: Bearer {token}"'
                    ' https://www.googleapis.com/oauth2/v1/tokeninfo')
    print(out)

  def write_outfile(self, out: str):
    """Write the outfile with build info if outfile is given.

    Args:
      out: filename to be written to
    """
    DIGESTSHA = self.sha_from_cloudbuild_out(out)
    if not self.output:
      print('No output file given, skipping output file writting.')
      return

    template = {'repository':
                {'hostname': self.registry_name,
                 'project': self.cloud_project
                 },
                'name': self.image_name,
                'digest': DIGESTSHA,
                'tags': [tag for tag in self.tags]
                }
    with open(self.output, 'w') as wf:
      json.dump(template, wf, indent=4)

  def sha_from_cloudbuild_out(self, out: str):
    """Find the "sha:foo" from the cloudbuild log."""
    DIGESTSHA = ''
    lines = out.split('\n')
    for i in range(len(lines) - 1, -1, -1):

      if lines[i] == 'DONE':
        if lines[i - 1] == 'PUSH':
          DIGESTSHA = (lines[i - 2].split('@')[-1])
    return DIGESTSHA.strip()

  def gcloud_build(self):
    """Build the Docker image using gcloud build.

    Assumes a cloudbuild.yaml is staged in the same dir as the given
    Dockerfile.
    """
    subs = self.structure_gcloud_tags()
    self.auth_gcloud()
    cloud_build_cmd = (
        f'gcloud builds submit --config {self.build_context}/cloudbuild.yaml'
        f' {self.build_context} --project {self.cloud_build_project}'
        f' --substitutions={subs}')

    print(f'Running cloud build cmd: {cloud_build_cmd}')
    print('\n\nNote: This can take a long time (>15 minutes)'
          ' for a large container that has no cache. Follow the link provided'
          ' a few lines below to see current progress of the build.'
          ' Build log follows:\n')
    # Stream the cloudbuild cmd.
    out, err, status = run(cloud_build_cmd, stream=True)
    if status != 0:
      raise GCloudBuildException(f'gcloud build failed with err:\n {err}\n')
    self.write_outfile(out)

  # Todo: this
  def docker_build(self):
    """Build the Docker image using Docker build."""
    raise Exception('Not impld.')
