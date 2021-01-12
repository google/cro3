#!/usr/bin/env python3
#
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Entry point for the forklift utility."""

import argparse
import sys

def command_gen_report(args):
    """Generates the commits missing between local and remote.

    Args:
        args: The arguments passed in by the user.

    Returns:
        0 if successful, non-zero otherwise.
    """
    raise NotImplementedError(args)

def command_cherry_pick(args):
    """Cherry-picks the commits in the forklift report to the local branch.

    Args:
        args: The arguments passed in by the user.

    Returns:
        0 if successful, non-zero otherwise.
    """
    raise NotImplementedError(args)

def command_complete_cherry_pick(args):
    """Marks a commit in the report as completed.

    Args:
        args: The arguments passed in by the user.

    Returns:
        0 if successful, non-zero otherwise.
    """
    raise NotImplementedError(args)

def command_resolve_conflict(args):
    """Help the user resolve the current conflict in the local tree.

    Args:
        args: The arguments passed in by the user.

    Returns:
        0 if successful, non-zero otherwise.
    """
    raise NotImplementedError(args)

def main(args):
    """Main function for forklift utility.

    Args:
        args: The arguments passed in by the user.

    Returns:
        0 if successful, non-zero otherwise.
    """
    desc = ('Utility to assist with backporting entire pull requests from '
            'upstream to the Chrome OS kernel.')

    parser_git = argparse.ArgumentParser(add_help=False)
    parser_git.add_argument('--git-path', '-g', type=str, default='.',
                            help='Path to git repository (if not current dir).')

    parser_report = argparse.ArgumentParser(add_help=False)
    parser_report.add_argument('--report-path', '-m', type=str, required=True,
                               help='Path to store forklift report file.')

    parser_commit = argparse.ArgumentParser(add_help=False)
    parser_commit.add_argument('--commit', type=str, default=None,
                               help='Git hash to identify a commit.')

    parser = argparse.ArgumentParser(description=desc)
    parser.set_defaults(func=None)
    subparsers = parser.add_subparsers(title='Sub-commands')

    subparser_gen = subparsers.add_parser('generate-report',
                        parents=[parser_git, parser_report],
                        help='Generate a forklift report from pull request.')
    subparser_gen.add_argument('--list', type=str, required=True,
                        help='Mailing list from lore.kernel.org/lists.html.')
    subparser_gen.add_argument('--msg-id', type=str, required=True,
                        help='Message-Id for the pull request to process.')
    subparser_gen.add_argument('--bug', type=str, default='None',
                        help='Value to use for BUG= in commit descriptions.')
    subparser_gen.add_argument('--test', type=str, default='None',
                        help='Value to use for TEST= in commit descriptions.')
    subparser_gen.add_argument('--common-ancestor', type=str, default=None,
                        help=('Optional common ancestor between the local and '
                              'remote trees. Improves execution time if '
                              'provided.'))
    subparser_gen.set_defaults(func=command_gen_report)

    subparser_pick = subparsers.add_parser('cherry-pick',
                        parents=[parser_git, parser_report],
                        help=('Cherry-pick commits in a forklift report.'))
    subparser_pick.set_defaults(func=command_cherry_pick)

    subparser_complete = subparsers.add_parser('complete-cherry-pick',
                        parents=[parser_report, parser_commit],
                        help=('Marks a commit as complete in an existing '
                              'forklift report'))
    subparser_complete.set_defaults(func=command_complete_cherry_pick)

    subparser_resolve = subparsers.add_parser('resolve',
                        parents=[parser_git],
                        help=('Utility to help resolve conflicts.'))
    subparser_resolve.set_defaults(func=command_resolve_conflict)

    args = parser.parse_args(args)
    if args.func:
        args.func(args)
    else:
        parser.print_help()

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
