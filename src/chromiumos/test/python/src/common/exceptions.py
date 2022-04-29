# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Custom Exception classes."""


class GCloudBuildException(Exception):
  """Raised when gcloud build fails"""
  pass  # pylint: disable=unnecessary-pass
