# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Custom Exception classes."""


class GCloudBuildException(Exception):
  """Raised when gcloud build fails"""
  pass  # pylint: disable=unnecessary-pass


class NotDirectoryException(Exception):
  """Raised when a file is found but is not a directory."""
  pass  # pylint: disable=unnecessary-pass


class ConfigError(Exception):
  """Raised when conflicting args."""
  pass  # pylint: disable=unnecessary-pass
