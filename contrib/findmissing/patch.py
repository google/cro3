# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Model containing data for patch database rows."""

from __future__ import print_function
from enum import Enum

class Status(Enum):
    """Status of gerrit change ticket."""

    OPEN = 1
    CLOS = 2
    PEND = 3
    ABAN = 4
    NONE = 5


class PatchEntry(object):
    """Data contained in a row of the Patches database."""

    downstream_sha = usha = fsha = downstream_changeid = fix_changeid = status = None

    def __init__(self, _downstream_sha, _usha, _fsha,
                _downstream_changeid, _fix_changeid, _status):
        self.downstream_sha = _downstream_sha # chromeos/stable sha
        self.usha = _usha # linux-upstream sha
        self.downstream_changeid = _downstream_changeid # gerrit chromeos/stable changeid
        self.fsha = _fsha # linux-upstream fix sha
        self.fix_changeid = _fix_changeid # gerrit fix changeid

        self.init_status(_status)


    def init_status(self, _status):
        """Status defined off existing gerrit ticket(changeid defined)"""
        self.status = _status if self.downstream_sha else None
