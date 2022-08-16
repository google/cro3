# Copyright 2022 The ChromiumOS Authors.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Pytest config."""

import pathlib
import site


site.addsitedir(pathlib.Path(__file__).parent)
