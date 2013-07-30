# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Some reasonable defaults for xBuddy path rewrites. Edit as you will.
def paths(board):
  return {
    # Used as the default for the update rpc.
    '': ['local', board, 'latest', 'test'],

    # Other overrides.
    'ld': ['local', board, 'latest', 'dev'],
    'stable-update' : ['remote', board, 'latest-stable', 'full_payload'],
    'beta-update' : ['remote', board, 'latest-beta', 'full_payload'],
    'dev-update' : ['remote', board, 'latest-dev', 'full_payload'],
    'canary' : ['remote', board, 'latest-canary', 'test'],
    'release' : ['remote', board, 'latest-official', 'test'],
    'paladin' : ['remote', board, 'latest-official-paladin', 'test'],
  }
