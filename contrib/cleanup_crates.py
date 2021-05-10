#!/usr/bin/env python3
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Find ebuilds for rust crates that have been replaced by newer versions.

Aids the process of removing unused rust ebuilds that have been replaced
by newer versions:

  1) Get the list of dev-rust ebuilds.
  2) Exclude the newest version of each ebuild.
  3) Generate a list of ebuilds that are installed for typical configurations.
  4) List the dev-rust ebuilds that aren't included.

For example:
  ./cleanup_crates.py -c --log-level=debug
"""

import distutils.version  # pylint: disable=no-name-in-module,import-error
import logging
import os
import pickle
import sys

from chromite.lib import build_target_lib
from chromite.lib import chroot_util
from chromite.lib import commandline
from chromite.lib import constants
from chromite.lib import osutils
from chromite.lib import portage_util

# The path of the cache.
DEFAULT_CACHE_PATH = os.path.join(osutils.GetGlobalTempDir(),
                                  'cleanup_crates.py')

# build targets to include for the host.
HOST_CONFIGURATIONS = {
    'virtual/target-sdk',
    'virtual/target-sdk-post-cross',
}
# build targets to include for each board.
BOARD_CONFIGURATIONS = {
    'virtual/target-os',
    'virtual/target-os-dev',
    'virtual/target-os-test',
}

# The set of boards to check. This only needs to be a representative set.
BOARDS = {'eve', 'tatl'} | (
    set() if not os.path.isdir(os.path.join(constants.SOURCE_ROOT, 'src',
                                            'private-overlays')) else
    {'lasilla-ground', 'mistral'}
)

_GEN_CONFIG = lambda boards, configs: [(b, c) for b in boards for c in configs]
# A tuple of (board, ebuild) pairs used to generate the set of installed
# packages.
CONFIGURATIONS = (
    _GEN_CONFIG((None,), HOST_CONFIGURATIONS) +
    _GEN_CONFIG(BOARDS, BOARD_CONFIGURATIONS)
)


def main(argv):
    """List ebuilds for rust crates replaced by newer versions."""
    opts = get_opts(argv)

    cln = CachedPackageLists(use_cache=opts.cache,
                             clear_cache=opts.clear_cache,
                             cache_dir=opts.cache_dir)

    ebuilds = exclude_latest_version(get_dev_rust_ebuilds())
    used = cln.get_used_packages(CONFIGURATIONS)

    unused_ebuilds = sorted(x.cpv for x in ebuilds if x.cpv not in used)
    print('\n'.join(unused_ebuilds))
    return 0


def get_opts(argv):
    """Parse the command-line options."""
    parser = commandline.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-c', '--cache', action='store_true',
        help='Enables caching of the results of GetPackageDependencies.')
    parser.add_argument(
        '-x', '--clear-cache', action='store_true',
        help='Clears the contents of the cache before executing.')
    parser.add_argument(
        '-C', '--cache-dir', action='store', default=DEFAULT_CACHE_PATH,
        type='path',
        help='The path to store the cache (default: %(default)s)')
    opts = parser.parse_args(argv)
    opts.Freeze()
    return opts


def get_dev_rust_ebuilds():
    """Return a list of dev-rust ebuilds."""
    return portage_util.FindPackageNameMatches('dev-rust/*')


def exclude_latest_version(packages):
    """Return a list of ebuilds that aren't the latest version."""
    latest = {}
    results = []
    lv = distutils.version.LooseVersion
    for pkg in packages:
        name = pkg.cp
        if name not in latest:
            latest[name] = pkg
            continue

        version = lv(pkg.version_no_rev)
        other_version = lv(latest[name].version_no_rev)
        if version > other_version:
            results.append(latest[name])
            latest[name] = pkg
        elif version != other_version:
            results.append(pkg)
    return results


def _get_package_dependencies(board, package):
    """List the ebuild-version dependencies for a specific board & package."""
    if board and not os.path.isdir(
            build_target_lib.get_default_sysroot_path(board)):
        chroot_util.SetupBoard(board, update_chroot=False,
                               update_host_packages=False,)
    return portage_util.GetPackageDependencies(board, package)


class CachedPackageLists:
    """Lists used packages with the specified cache configuration."""

    def __init__(self, use_cache=False, clear_cache=False,
                 cache_dir=DEFAULT_CACHE_PATH):
        """Initialize the cache if it is enabled."""
        self.use_cache = bool(use_cache)
        self.clear_cache = bool(clear_cache)
        self.cache_dir = cache_dir
        if self.clear_cache:
            osutils.RmDir(self.cache_dir, ignore_missing=True)
        if self.use_cache:
            osutils.SafeMakedirs(self.cache_dir)

    def _try_cache(self, name, fn):
        """Caches the return value of a function."""
        if not self.use_cache:
            return fn()

        try:
            with open(os.path.join(self.cache_dir, name), 'rb') as fp:
                logging.info('cache hit: %s', name)
                return pickle.load(fp)
        except FileNotFoundError:
            pass

        logging.info('cache miss: %s', name)
        result = fn()

        with open(os.path.join(self.cache_dir, name), 'wb+') as fp:
            pickle.dump(result, fp)

        return result

    def get_used_packages(self, configurations):
        """Return the packages installed in the specified configurations."""

        def get_deps(board, package):
            filename_package = package.replace('/', ':')
            return self._try_cache(
                f'deps:{board}:{filename_package}',
                lambda: _get_package_dependencies(board, package))

        used = set()
        for board, package in configurations:
            deps = get_deps(board, package)
            if deps:
                used.update(deps)
            else:
                logging.warning('No depts for (%s, %s)', board, package)
        return used


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
