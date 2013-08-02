# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Some reasonable defaults for xBuddy path rewrites. Edit as you will.
def paths():
  return {
    # Used as the default for the update rpc.
    '': 'local/%(board)s/latest/test',

    # Other overrides.
    'update': 'local/%(board)s/latest/full_payload',
    'ld': 'local/%(board)s/latest/dev',
    'stable-update' : 'remote/%(board)s/latest-stable/full_payload',
    'beta-update' : 'remote/%(board)s/latest-beta/full_payload',
    'dev-update' : 'remote/%(board)s/latest-dev/full_payload',
    'canary' : 'remote/%(board)s/latest-canary/test',
    'release' : 'remote/%(board)s/latest-official/test',
    'paladin' : 'remote/%(board)s/latest-official-paladin/test',
  }
