# Commits to revert on each topic branch *before* topic fixups
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Useless lints.
# pylint: disable=line-too-long
# pylint: disable=input-builtin

"""Various hooks to aid the rebase, see rebase_config.py for usage"""


def pause(sha, hook_type):
    """Pauses execution"""

    print("Rebase paused by the `pause` hook.")
    print(
        "Note: depending on the moment the hook is called different invariants apply"
    )
    print(
        "    * pre/post/post_empty: repository must be in a clean state, with every change commited"
    )
    print(
        "    * conflict: no guarantees, only inspect the state of the repository unless you know what you're doing"
    )
    print("SHA:", sha)
    print("Hook type:", hook_type)
    print("Press enter when you're ready to proceed")
    input()
