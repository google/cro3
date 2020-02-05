# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Model containing data for patch database rows."""

from __future__ import print_function
from enum import Enum


def make_patch_table(c):
    """Create database table."""

    c.execute('CREATE TABLE patches ('
            'downstream_sha text,'
            'usha text,'
            'fix_usha text,'
            'downstream_link text,'
            'fix_link text,'
            'status char(4))')

    c.execute('CREATE TABLE statistics ('
            'day int,'
            'clean_fix_count int,'
            'fail_fix_count text)')


class Status(Enum):
    """Status of gerrit change ticket."""

    OPEN = 1 # Gerrit ticket was created for clean fix patch
    CLOS = 2 # Gerrit ticket was merged and closed
    ABAN = 3 # Gerrit ticket was abandoned
    CONF = 4 # Gerrit ticket NOT created since patch doesn't apply properly


class PatchEntry(object):
    """Data contained in a row of the Patches database."""

    downstream_sha = usha = fsha = downstream_link = fix_link = status = None

    def __init__(self, _downstream_sha, _usha, _fsha,
                _downstream_link, _fix_link, _status):
        self.downstream_sha = _downstream_sha # chromeos/stable sha
        self.usha = _usha # linux-upstream sha
        self.downstream_link = _downstream_link # gerrit chromeos/stable link
        self.fsha = _fsha # linux-upstream fix sha
        self.fix_link = _fix_link # gerrit fix link
        self.status = _status # status of attempted cherrypick


    def set_downstream_sha(self, _downstream_sha):
        """Constructor for downstream_sha"""
        self.downstream_sha = _downstream_sha

    def set_downstream_link(self, _downstream_link):
        """Constructor for downstream_link"""
        self.downstream_link = _downstream_link

    def set_fix_link(self, _fix_link):
        """Constructor for fix_link"""
        self.fix_link = _fix_link

    def set_status(self, _status):
        """Constructor for status"""
        self.status = _status
