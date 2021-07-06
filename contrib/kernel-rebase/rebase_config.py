# Commits to revert on each topic branch *before* topic fixups
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""automatic rebase-specific data"""

global_reverts = []

topic_fixups = {}
# example:
# topic_fixups['bluetooth'] = ['fd83ec5d9b94']

# order for automatic branch merging in rebase.py.
# branches that aren't specified are merged in an unspecified order.
# example that first merges drm, then gpu/other, then others:
# merge_order_override = [
#     "drm",
#     "gpu/other"
# ]
merge_order_override = [
]

# patches to be cherry-picked after automatic merge
# example:
# merge_fixups = [
#     "e0783589ae58"
# ]
merge_fixups = [
]

# cherry-pick a list of patches before a given patch
# during automatic rebase.
# example:
# patch_deps = {
#     '0d022b4a1e19': ['6e18e51a1c19']
# }
patch_deps = {
}

# Add entry here to overwrite default disposition on particular commit
# WARNING: lines can be automatically appended here when user chooses
# to drop the commit from rebase script.
disp_overlay = {}
# example
# disp_overlay['62b865c66db4'] = 'drop'
