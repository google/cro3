# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Base Prep for Docker Build context creation."""

import os

# The default yaml for all current CFT builders.
YAML_TEMPLATE = """
substitutions:
{subs}
steps:
- name: 'gcr.io/kaniko-project/executor:latest'
  args:
    [
      "--dockerfile=Dockerfile",
      "--context=.",
      "--cache=true",
      "--cache-ttl=366h",
      "--image-fs-extract-retry=2",
{destinations}
{labels}
    ]
  timeout: 1800s
options:
  logging: CLOUD_LOGGING_ONLY
"""

SUB_VAR = '__BUILD_TAG{n}'
LABEL_SUB_VAR = '__LABEL{n}'
SUB_TEMPLATE = '  {var}: ""\n'
DESTINATION_VAR = '      "--destination=${{{var}}}",\n'
LABEL_VAR = '      "--label=${{{var}}}",\n'


class BaseDockerPrepper():
  """Prep Needed files for the Test Execution Container Docker Build."""

  def __init__(self,
               chroot: str,
               sysroot: str,
               tags: str,
               labels: str,
               service: str):
    """@param args (ArgumentParser): .chroot, .sysroot, .path."""
    self.tags = tags.split(',') if tags else []
    self.labels = labels.split(',') if labels else []
    self.chroot = chroot
    self.sysroot = sysroot
    self.outputdir = f'tmp/docker/{service}'
    self.service = service

    if self.sysroot.startswith('/'):
      self.sysroot = self.sysroot[1:]
    self.full_out_dir = os.path.join(self.chroot, self.sysroot, self.outputdir)

  def prep_container(self):
    """To be implemented by child class."""
    raise NotImplementedError

  def build_yaml(self):
    """Construct and write the YAML into the docker context dir"""
    subs = ''
    destinations = ''
    labels = ''

    # Always add in atleast 1 tag. If none are given, 1 will be added by the
    # builder by default, so ensure the cloudbuild yaml can support it.
    for i in range(max(len(self.tags), 1)):
      var = SUB_VAR.format(n=i)
      subs += SUB_TEMPLATE.format(var=var)
      destinations += DESTINATION_VAR.format(var=var)

    for i in range(len(self.labels)):
      var = LABEL_SUB_VAR.format(n=i)
      subs += SUB_TEMPLATE.format(var=var)
      labels += LABEL_VAR.format(var=var)

    cloudbuild_yaml = YAML_TEMPLATE.format(subs=subs,
                                           destinations=destinations,
                                           labels=labels)

    with open(os.path.join(self.full_out_dir, 'cloudbuild.yaml'), 'w') as wf:
      wf.write(cloudbuild_yaml)
      print(f'wrote yaml to {wf}')
