#!/usr/bin/env python3
#
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Entry point for the forklift utility."""

import argparse
import json
import pathlib
import re
import sys

from git import Git
from pull_request import PullRequest
from resolver import Resolver

class ForkliftReport:
    """Encapsulates a forklift report.

    Attributes:
        bug: The value of BUG= field in the commit messages.
        test: The value of TEST= field in the commit messages.
        commits: A list of the commits in the report.
    """
    class Commit:
        """Encapsulates a commit within the forklift report.

        Attributes:
            sha: The git hash used to identify the commit.
            backported: True if the patch is present in the local branch.
        """
        def __init__(self, sha, backported):
            self.sha = sha
            self.backported = backported

    def __init__(self, report_path, prefix=None, bug=None, test=None, tree=None):
        """Initializes the forklift report.

        Args:
            report_path: The patch of the report file.
            bug: The value of BUG= field in the commit messages.
            test: The value of TEST= field in the commit messages.
        """
        self._path = report_path
        self.prefix = prefix
        self.bug = bug
        self.test = test
        self.tree = tree
        self.commits = []

    def save(self):
        """Saves the report to the path given at init."""
        output = {'prefix': self.prefix, 'bug': self.bug, 'test': self.test,
                  'tree': self.tree, 'commits': []}
        for c in self.commits:
            output['commits'].append(c.__dict__)

        with open(self._path, mode='w') as f:
            json.dump(output, f, indent=2)

    def load(self):
        """Loads the report from the file path given at init.

        Returns:
            True if the file was loaded, False otherwise.
        """
        try:
            with open(self._path, mode='rb') as f:
                j = json.load(f)

            self.prefix = j['prefix']
            self.bug = j['bug']
            self.test = j['test']
            self.tree = j['tree']
            for c in j['commits']:
                self.commits.append(ForkliftReport.Commit(c['sha'],
                                                          c['backported']))

            return True
        except FileNotFoundError:
            return False

    def add_commit(self, sha, backported=False):
        """Adds a commit to the report.

        Args:
            sha: The git hash of the commit to be added.
            backported: True if the commit already exists in the local branch.
        """
        self.commits.append(ForkliftReport.Commit(sha, backported))

def menu(instruction, options):
    """Asks the user to choose an option.

    Args:
        instruction: The text string to show with the input prompt.
        options: A list of option tuples (shortcut, option) to show the user.

    Returns:
        A tuple of the option idx and value chosen by the user.
    """
    if len(options) == 1:
        return (0, options[0][0])

    print('')
    for i, o in enumerate(options):
        print(f' {o[0]: <3} - {o[1]}')

    while True:
        # pylint: disable=input-builtin
        choice = input(f'{instruction}: ').strip()
        print('')

        for i, o in enumerate(options):
            if choice == o[0]:
                choice = i
                break

        if choice is None:
            print('Invalid input, please choose one of the options!')
            continue

        return (choice, options[choice])

def confirm(prompt='Are you sure?'):
    """Asks the user to confirm the action they're about to undertake.

    Returns:
        True if the answer is yes, False if the answer is no.
    """
    while True:
        # pylint: disable=input-builtin
        choice = input(f'{prompt} [Y/n]')
        print('')
        if choice.lower() in ['y', 'yes', '']:
            return True
        if choice.lower() in ['n', 'no']:
            return False

def command_gen_report(args):
    """Generates the commits missing between local and remote.

    Args:
        args: The arguments passed in by the user.

    Returns:
        0 if successful, non-zero otherwise.
    """

    """Python doesn't support nesting of mutually exclusive arg groups yet
    (https://bugs.python.org/issue10984), so we have to do this by hand
    """
    if not args.list and not args.msg_id and not args.local_pull:
        raise ValueError('Must specify a pull request from the list or local.')
    if (args.list or args.msg_id) and args.local_pull:
        raise ValueError('Cannot specify a pull request from list and local.')
    if (args.list and not args.msg_id) or (not args.list and args.msg_id):
        raise ValueError('List and Message-Id must both be specified.')

    report = ForkliftReport(args.report_path, args.prefix, args.bug, args.test,
                            args.tree)
    pull_request = PullRequest(args.list, args.msg_id, args.local_pull)
    git = Git(args.git_path)
    if not git.fetch_refspec_from_remote(pull_request.source_tree,
                                         pull_request.source_ref):
        print(f'Failed to fetch {pull_request.source_ref} from '
              f'{pull_request.source_tree}')
        return 1

    commits = git.get_commits_in_range(pull_request.base_commit,
                                       pull_request.end_commit)
    print(f'Found {len(commits)} total commits in the pull request')

    commits.reverse()

    for c in commits:
        b = git.commit_in_local_branch(c, args.common_ancestor, False)
        print(f'Adding commit={c} backported={b}')
        report.add_commit(c, b)

    report.save()

    return 0

def _format_commit_message(git, report, message, conflicted):
    msg = message.rstrip().splitlines()
    if conflicted:
        if not msg[0].startswith('BACKPORT'):
            msg[0] = f'BACKPORT/{report.prefix}: ' + msg[0]
    else:
        msg[0] = f'{report.prefix}: ' + msg[0]

    forklift_sig = 'Backported using forklift.py'
    re_cp = re.compile('\(cherry picked from commit ([0-9a-fA-F]+)\)')

    found = {'bug': None, 'test': None, 'cherry-pick': None, 'change-id': None,
             'forklift': None}
    for i, l in enumerate(msg[1:]):
        if l.startswith('BUG='):
            found['bug'] = i + 1
        elif l.startswith('TEST='):
            found['test'] = i + 1
        elif l.startswith('Change-Id'):
            found['change-id'] = i + 1
        elif re_cp.fullmatch(l):
            found['cherry-pick'] = i + 1
        elif l.startswith(forklift_sig):
            found['forklift'] = i + 1

    # If found[change-id] is not the max of all other indices, this Change-id
    # likely is from the upstream commit, so let's generate a new Change-id.
    max_index = max([v for v in found.values() if v])
    change_id = ''
    if found['change-id'] and (found['change-id'] == max_index):
        change_id = msg.pop(found['change-id'])
    else:
        ret, cid = git.generate_change_id()
        if ret:
            change_id = f'Change-Id: {cid}'

    cherry_pick = ''
    if found['cherry-pick']:
        m = re_cp.fullmatch(msg.pop(found['cherry-pick']))
        cherry_pick = f'(cherry picked from commit {m.group(1)}'
        if report.tree:
            msg.insert(found['cherry-pick'], cherry_pick)
            msg.insert(found['cherry-pick'] + 1, f' {report.tree})')
        else:
            msg.insert(found['cherry-pick'], cherry_pick + ')')
    else:
        raise ValueError('Could not find cherry pick string!')

    if not found['bug'] or not found['test']:
        msg.append('')

    if not found['bug']:
        msg.append(f'BUG={report.bug}')
    if not found['test']:
        msg.append(f'TEST={report.test}')
    if not found['forklift']:
        msg.append('')
        msg.append(forklift_sig)

    if change_id:
        msg.append('')
        msg.append(change_id)

    return '\n'.join(msg)

def command_cherry_pick(args):
    """Cherry-picks the commits in the forklift report to the local branch.

    Args:
        args: The arguments passed in by the user.

    Returns:
        0 if successful, non-zero otherwise.
    """
    report = ForkliftReport(args.report_path)
    git = Git(args.git_path)

    if not report.load():
        print(f'Could not load the report at {args.report_path}')
        return 1

    i = 0
    for c in report.commits:
        i += 1
        pfx = f'[{i:>4}/{len(report.commits)}]'
        if c.backported:
            continue

        if git.commit_in_local_branch(c.sha, include_cherry_picks=True):
            print(f'{pfx} {c.sha} in local branch')
            c.backported = True
            report.save()
            continue

        print(f'{pfx} Cherry-picking change {c.sha}')
        ret, skipped = git.cherry_pick(c.sha, skip_empty=True)
        conflicted = False
        if not ret:
            print(f'    Cherry-pick {c.sha} failed, conflicting files:')
            for f in git.get_conflicting_files():
                print(f'      {f}')

            idx, _ = menu('Please resolve the conflict and choose an option',
                          [('c', 'Conflict resolved, patch is HEAD. Continue'),
                           ('s', 'Patch was not needed. Skip it.'),
                           ('q', 'Quit')])
            if idx == 0:
                conflicted = True
            elif idx == 1:
                skipped = True
            else:
                print(('Hint #1: If you commit the change outside of this '
                       'utility, ensure you add the appropriate subject '
                       'prefix/BUG/TEST/Change-Id to the commit msg.'))
                print(('Hint #2: If you skip this commit, use the '
                       '"complete-cherry-pick" subcommand to skip this commit '
                       'on subsequent cherry-pick runs'))
                return 1

        if not skipped:
            ret, msg = git.get_commit_message()
            if ret:
                msg = _format_commit_message(git, report, msg, conflicted)
                git.set_commit_message(msg)

        c.backported = True
        report.save()

    return 0

def command_complete_cherry_pick(args):
    """Marks a commit in the report as completed.

    Args:
        args: The arguments passed in by the user.

    Returns:
        0 if successful, non-zero otherwise.
    """
    report = ForkliftReport(args.report_path)

    if not report.load():
        print(f'Could not load the report at {args.report_path}')
        return 1

    commit = None
    for c in report.commits:
        if args.commit:
            if c.sha.startswith(args.commit):
                commit = c
                break
        else:
            if not c.backported:
                if confirm(f'Would you like to complete {c.sha}?'):
                    commit = c
                    break

                return 1

    if commit:
        commit.backported = True
        report.save()
    return 0

def command_resolve_conflict(args):
    """Help the user resolve the current conflict in the local tree.

    Args:
        args: The arguments passed in by the user.

    Returns:
        0 if successful, non-zero otherwise.
    """
    git = Git(args.git_path)
    conflict_files = git.get_conflicting_files()

    if not conflict_files:
        print('No conflicting files found.')
        return 1

    while True:
        options = [(str(i + 1), x) for i, x in enumerate(conflict_files)]
        idx, choice = menu('Choose a file to resolve',
                           (options + [('q', 'Quit')]) if len(conflict_files) > 1 else options)
        if choice == 'q':
            return 0

        path = options[idx][1]
        while True:
            print(f'Attempting to resolve conflicts in {path}')
            resolver = Resolver(git, str(pathlib.Path(args.git_path, path)))
            conflicts = resolver.get_conflicts()

            if not conflicts:
                print('No conflicts found!')
                return 1

            line_choices = [(str(i + 1), f'Line {x.head()}')
                            for i, x in enumerate(conflicts)]

            idx, choice = menu('Choose a conflict to resolve',
                               line_choices +
                               [('bh', 'Blame file HEAD'),
                                ('br', 'Blame file remote'),
                                ('b', 'Back'),
                                ('q', 'Quit')])
            if choice[0] == 'b':
                break
            if choice[0] == 'q':
                return 0
            if choice[0] == 'bh':
                print(git.blame(path, 'HEAD'))
                continue
            if choice[0] == 'br':
                print(git.blame(path, f'{conflicts[0].sha}'))
                continue

            conflict = conflicts[idx]

            while True:
                _, choice = menu('Choose an action',
                                 [('c', 'Print conflict'),
                                  ('h', 'Print head'),
                                  ('r', 'Print remote'),
                                  ('rc', 'Print remote commit'),
                                  ('bh', 'Blame head'),
                                  ('br', 'Blame remote'),
                                  ('cc', 'Compare commits between head/remote'),
                                  ('b', 'Back'),
                                  ('q', 'Quit')])
                if choice[0] == 'c':
                    print(resolver.format_conflict(conflict))
                elif choice[0] == 'h':
                    print(resolver.format_conflict(conflict,
                                                   print_remote=False))
                elif choice[0] == 'r':
                    print(resolver.format_conflict(conflict, print_head=False))
                elif choice[0] == 'rc':
                    print(git.show(conflict.sha))
                elif choice[0] == 'bh':
                    print(resolver.blame_head(conflict))
                elif choice[0] == 'br':
                    print(resolver.blame_remote(conflict))
                elif choice[0] == 'cc':
                    print(resolver.compare_commits(conflict))
                elif choice[0] == 'b':
                    break
                elif choice[0] == 'q':
                    return 0

    return 0

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
    subparser_gen.add_argument('--list', type=str,
                        help='Mailing list from lore.kernel.org/lists.html.')
    subparser_gen.add_argument('--msg-id', type=str,
                        help='Message-Id for the pull request to process.')
    subparser_gen.add_argument('--local-pull', type=str,
                               help='Path to a local pull request.')
    subparser_gen.add_argument('--bug', type=str, default='None',
                        help='Value to use for BUG= in commit descriptions.')
    subparser_gen.add_argument('--test', type=str, default='None',
                        help='Value to use for TEST= in commit descriptions.')
    subparser_gen.add_argument('--common-ancestor', type=str, default=None,
                        help=('Optional common ancestor between the local and '
                              'remote trees. Improves execution time if '
                              'provided.'))
    subparser_gen.add_argument('--prefix', type=str, default='UPSTREAM',
                        help=('Optional subject prefix to use for forklifted '
                              'patches. Defaults to "UPSTREAM"'))
    subparser_gen.add_argument('--tree', type=str, default=None,
                        help=('Optional tree to use in the "cherry picked" '
                              'line in the commit message. Defaults to empty.'))
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
