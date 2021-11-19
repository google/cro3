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
import collections
import errno
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
from chromite.lib.parser import package_info

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
    {'brya-manatee', 'kiran', 'mistral', 'reven'}
)

_GEN_CONFIG = lambda boards, configs: [(b, c) for b in boards for c in configs]
# A tuple of (board, ebuild) pairs used to generate the set of installed
# packages.
CONFIGURATIONS = (
    _GEN_CONFIG((None,), HOST_CONFIGURATIONS) +
    _GEN_CONFIG(BOARDS, BOARD_CONFIGURATIONS)
)

EBUILD_SUFFIX = '.ebuild'

def main(argv):
    """List ebuilds for rust crates replaced by newer versions."""
    opts = get_opts(argv)

    cln = CachedPackageLists(use_cache=opts.cache,
                             clear_cache=opts.clear_cache,
                             cache_dir=opts.cache_dir)

    ebuilds = get_dev_rust_ebuilds()
    used = cln.get_used_packages(CONFIGURATIONS)
    if not opts.latest:
        used.update(latest_versions(ebuilds))

    for key, value in find_ebuild_symlinks(ebuilds).items():
        if key in used and value not in used:
            logging.info('Used symlink to unused cpvr: %s -> %s', key, value)
            used.add(value)

    used_pv = set()
    unused_ebuilds = []
    for ebuild in ebuilds:
        if ebuild.cpvr not in used:
            unused_ebuilds.append(ebuild)
        else:
            used_pv.add(ebuild.pv)
    print('\n'.join(sorted(x.cpvr for x in unused_ebuilds)))

    if opts.apply:
        remove_ebuilds(unused_ebuilds)
        remove_manifest_entries([x for x in unused_ebuilds
                                 if x.pv not in used_pv])
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
    parser.add_argument(
        '-A', '--apply', action='store_true',
        help='Remove the ebuilds and their Manifest entries.')
    parser.add_argument(
        '-L', '--latest', action='store_true',
        help='Remove even the latest version of unused ebuilds')
    opts = parser.parse_args(argv)
    opts.Freeze()
    return opts


def get_dev_rust_ebuilds():
    """Return a list of dev-rust ebuilds excluding cros-workon packages."""
    results = []
    category = 'dev-rust'
    category_dir = os.path.join(constants.SOURCE_ROOT,
                                constants.CHROMIUMOS_OVERLAY_DIR,
                                category)
    for package in os.listdir(category_dir):
        package_dir = os.path.join(category_dir, package)
        if not os.path.isdir(package_dir):
            continue
        # Skip cros-workon packages.
        if os.path.exists(os.path.join(package_dir,
                                       '%s-9999.ebuild' % package)):
            continue
        for ebuild_name in os.listdir(package_dir):
            if not ebuild_name.lower().endswith(EBUILD_SUFFIX):
                continue
            cpvr = os.path.join(category,
                                ebuild_name[0:-len(EBUILD_SUFFIX)])
            results.append(package_info.parse(cpvr))
    return results


def latest_versions(packages):
    """Return a list of the pvr's with the latest version."""
    by_atom = collections.defaultdict(list)
    for pkg in packages:
        by_atom[pkg.atom].append(pkg)
    results = []
    # Pick out all the old versions, but keep different revisions of the newest
    # version to ensure we don't keep a symlink and remove the ebuild itself.
    for pkgs in by_atom.values():
        pkgs.sort()
        results.append(pkgs[-1].cpvr)
    return results


def _get_package_dependencies(board, package):
    """List the ebuild-version dependencies for a specific board & package."""
    if board and not os.path.isdir(
            build_target_lib.get_default_sysroot_path(board)):
        chroot_util.SetupBoard(board, update_chroot=False,
                               update_host_packages=False,)
    return portage_util.GetPackageDependencies(board, package)


def get_ebuild_path(package):
    """Get the absolute path to a chromiumos-overlay ebuild."""
    return os.path.join(constants.SOURCE_ROOT,
                        constants.CHROMIUMOS_OVERLAY_DIR,
                        package.relative_path)


def chase_references(references):
    """Flatten a pvr -> pvr dict."""
    to_chase = set(references.keys())
    while to_chase:
        value = to_chase.pop()
        stack = [value]
        value = references[value]
        while value in to_chase:
            to_chase.remove(value)
            stack.append(value)
            value = references[value]
        for key in stack:
            references[key] = value


def find_ebuild_symlinks(packages):
    """Resolve ebuild symlinks as a flattened pvr -> pvr dict."""
    links = {}
    checked = set()
    for package in packages:
        if package.cp in checked:
            continue
        checked.add(package.cp)
        ebuild_dir = os.path.dirname(get_ebuild_path(package))
        __find_ebuild_symlinks_impl(ebuild_dir, links)
    chase_references(links)
    return links


def __find_ebuild_symlinks_impl(ebuild_dir, links):
    package = os.path.basename(ebuild_dir)
    category = os.path.basename(os.path.dirname(ebuild_dir))
    for ebuild_name in os.listdir(ebuild_dir):
        if not ebuild_name.lower().endswith(EBUILD_SUFFIX):
            continue
        ebuild_path = os.path.join(ebuild_dir, ebuild_name)
        if not os.path.islink(ebuild_path):
            continue
        target = os.path.realpath(ebuild_path)
        target_name = os.path.basename(target)
        prefix = '%s-' % package
        if (os.path.dirname(target) != ebuild_dir or
            not target_name.startswith(prefix) or
            not target_name.lower().endswith(EBUILD_SUFFIX)):
            logging.warning('Skipping symlink: %s -> %s', ebuild_path, target)
            continue
        cpvr = os.path.join(category,
                            ebuild_name[0:-len(EBUILD_SUFFIX)])
        target_cpvr = os.path.join(category,
                                   target_name[0:-len(EBUILD_SUFFIX)])
        links[cpvr] = target_cpvr


def remove_ebuilds(packages):
    """Removes the listed ebuilds."""
    for package in packages:
        ebuild_path = get_ebuild_path(package)
        ebuild_dir = os.path.dirname(ebuild_path)
        logging.info('Removing: %s', ebuild_path)
        try:
            os.unlink(ebuild_path)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
            logging.warning('Could not find: %s', ebuild_path)
        try:
            os.rmdir(ebuild_dir)
        except OSError as e:
            if e.errno != errno.ENOTEMPTY:
                raise


def remove_manifest_entries(packages):
    """Removes the manifest entries for the listed ebuilds."""
    for package in packages:
        ebuild_dir = os.path.dirname(get_ebuild_path(package))
        manifest_path = os.path.join(ebuild_dir, 'Manifest')
        if not os.path.exists(manifest_path):
            logging.warning('Could not find: %s', manifest_path)
            continue
        logging.info('Updating: %s', manifest_path)
        with open(manifest_path, 'r') as m:
            manifest_lines = m.readlines()
        filtered_lines = [a for a in manifest_lines if package.pv not in a]
        if not filtered_lines:
            os.remove(manifest_path)
        elif len(filtered_lines) != len(manifest_lines):
            with open(manifest_path, 'w') as m:
                for line in filtered_lines:
                    m.write(line)
        try:
            os.rmdir(ebuild_dir)
        except OSError as e:
            if e.errno != errno.ENOTEMPTY:
                raise


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
