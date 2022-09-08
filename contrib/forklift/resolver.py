# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides help with the conflict resolution feature of forklift"""

from collections import defaultdict
from datetime import datetime
import re

class Commit:
    """Represents a commit object.

    Attributes:
        sha: The commit sha.
        author: The commit author.
        date_authored: The author date.
    """
    def __init__(self, sha, author, date_authored):
        self._sha = sha
        self._author = author
        self._date_authored = date_authored

    @staticmethod
    def from_blame_line(blame_line):
        pat_sha = '([a-f0-9]+)'
        pat_file = '.*?\s*'
        pat_author = '(.*?)'
        pat_date = '[0-9]{4}-[0-9]{2}-[0-9]{2}'
        pat_time = '[0-9]{2}:[0-9]{2}:[0-9]{2} [+-][0-9]{4}'
        pat_datetime = f'({pat_date} {pat_time})\s*[0-9]*'
        pat_details = rf'\({pat_author} {pat_datetime}\)'
        pattern = f'{pat_sha}{pat_file} {pat_details}'
        m = re.match(pattern, blame_line)
        if not m:
            return None

        sha = m.group(1).strip()
        author = m.group(2).strip()
        date = datetime.strptime(m.group(3).strip(), '%Y-%m-%d %H:%M:%S %z')
        return Commit(sha, author, date)

class Conflict:
    """Represents a conflict located in a local file.

    Attributes:
        sha: The upstream commit sha involved in the conflict.
        subject: The upstream commit subject.
        head_confict: List of the head lines involved in the conflict.
        remote_conflict: The lines from the remote which are conflicting.
    """
    def __init__(self, head=None, separator=None, remote=None):
        """Initialize the conflict object.

        Args:
            head: The line number of the '<<<<<<< HEAD' sentinel.
            separator: The line number of the '=======' sentinel.
            remote: The line number of the '>>>>>>> <sha>...<subject' sentinel.
        """
        self._head = None
        self._separator = None
        self._remote = None

        self.sha = None
        self.subject = None
        self.head_conflict = []
        self.remote_conflict = []

        self._set_head(head)
        self._set_separator(separator)
        self._set_remote(remote)

    @staticmethod
    def _valid_conflict(head, separator, remote):
        valid = True
        if separator:
            valid = valid and head and head < separator
        if remote:
            valid = valid and separator and separator < remote
        return valid

    def _set_head(self, head):
        if not self._valid_conflict(head, self._separator, self._remote):
            raise ValueError((f'Conflict {head}/{self._separator}/'
                                f'{self._remote} invalid.'))
        self._head = head

    def _set_separator(self, separator):
        if not self._valid_conflict(self._head, separator, self._remote):
            raise ValueError((f'Conflict {self._head}/{separator}/'
                                f'{self._remote} invalid.'))
        self._separator = separator

    def _set_remote(self, remote):
        if not self._valid_conflict(self._head, self._separator, remote):
            raise ValueError((f'Conflict{self._head}/{self._separator}/'
                                f'{remote} invalid.'))
        self._remote = remote

    def head(self):
        """Returns the line number of '<<<<<<< HEAD' for the conflict."""
        return self._head

    def separator(self):
        """Returns the line number of '=======' for the conflict."""
        return self._separator

    def remote(self):
        """Returns the line number of '>>>>>>>' for the conflict."""
        return self._remote

    def parse(self, line_num, line):
        """Parses the line and adds it to the internal state if applicable.

        Args:
            line_num: The number of the line being parsed.
            line: The contents of the current line being parsed.

        Returns:
            True if the conflict has been completely parsed, False otherwise.
        """
        if line.startswith('<<<<<<<'):
            self._set_head(line_num)
        elif line.startswith('======='):
            self._set_separator(line_num)
        elif line.startswith('>>>>>>>'):
            self._set_remote(line_num)
            m = re.match(r'>>>>>>> ([a-f0-9]+)(\.{3})? \(?(.+)\)?\n', line)
            self.sha = m.group(1)
            self.subject = m.group(3)
            return True
        elif self._head and not self._separator:
            self.head_conflict.append(line.rstrip())
        elif self._separator and not self._remote:
            self.remote_conflict.append(line.rstrip())

        return False

class Resolver:
    """Class to assist in resolving a conflict."""
    def __init__(self, git, path):
        """Initialize the Resolver class.

        Args:
            git: The Git object to use for git operations.
            path: The path of the file containing the conflicts to resolve.
        """
        self._git = git
        self._path = path

    def get_conflicts(self):
        """Returns a list of conflicts from the file at the given path.

        Parses the file at self._path and pulls out all the conflicts
        into Conflict objects. Returns a list of those conflicts.

        Args:
            path: The path to the conflicting file.

        Returns:
            A list of conflicts from the given file.
        """
        conflicts = []
        with open(self._path, mode='r') as f:
            cur_conflict = Conflict()
            line_num = 1
            for l in f:
                if cur_conflict.parse(line_num, l):
                    conflicts.append(cur_conflict)
                    cur_conflict = Conflict()
                line_num += 1

        return conflicts

    @staticmethod
    def _format_conflict_line(line_num, line):
        return f'{line_num:<5} {line}\n'

    def format_conflict(self, conflict, print_head=True, print_remote=True):
        """Formats the conflict in a human-readable format.

        Args:
            conflict: The Conflict object to format.
            print_head: True if output should contain the HEAD portion.
            print_remote: True if output should contain the remote portion.

        Returns:
            The formatted conflict in a string.
        """
        ret = ''
        if print_head:
            ret += self._format_conflict_line(conflict.head(), '<<<<<<< HEAD')

            for i, l in enumerate(conflict.head_conflict):
                ret += self._format_conflict_line(i + 1 + conflict.head(), l)

        ret += self._format_conflict_line(conflict.separator(), '=======')

        if print_remote:
            for i, l in enumerate(conflict.remote_conflict):
                ret += self._format_conflict_line(i + 1 + conflict.separator(),
                                                  l)

            ret += self._format_conflict_line(conflict.remote(),
                                f'>>>>>>> {conflict.sha}.. {conflict.subject}')

        return ret

    def blame_head(self, conflict):
        """Fetch the git blame output for the HEAD portion of the conflict.

        Args:
            conflict: The Conflict object to assign blame.

        Returns:
            String containing the git blame output for the conflict's HEAD text.
        """
        blame = self._git.blame(self._path).splitlines()

        # 3 lines of context on either side
        start = max(0, conflict.head() - 4)
        end = conflict.head() - 1
        ret = '\n'.join(blame[start:end])
        ret += '\n'

        start = conflict.head()
        end = conflict.separator() - 1
        ret += '\n'.join(blame[start:end])
        ret += '\n'

        start = min(len(blame), conflict.remote())
        end = min(len(blame), conflict.remote() + 3)
        ret += '\n'.join(blame[start:end])

        return ret

    @staticmethod
    def _get_diff_chunks(diff):
        re_chunk = re.compile((r'@@ -([0-9]+),([0-9]+) \+([0-9]+),([0-9]+) @@'
                                '(.*)?'))

        chunks = []
        cur_chunk = None
        for l in diff.splitlines():
            m = re_chunk.match(l)
            if m:
                if cur_chunk:
                    chunks.append(cur_chunk)

                cur_chunk = {'old_line': int(m.group(1)),
                             'old_num': int(m.group(2)),
                             'new_line': int(m.group(3)),
                             'new_num': int(m.group(4)),
                             'identifier': m.group(5) if m.group(5) else 'NA',
                             'chunk': [],
                             'score': 0}
            else:
                cur_chunk['chunk'].append(l.rstrip())

        if cur_chunk:
            chunks.append(cur_chunk)

        return chunks

    def _score_chunks_by_identifier(self, conflict, chunk_list):
        # Walk through the local file backwards starting at the conflict
        # looking for the first identifier also showing up in the git diff
        # output for the conflicting change. Score one point to any chunk with
        # the same identifier
        with open(self._path, 'r') as f:
            lines = f.readlines()

        identifier = None
        for l in reversed(lines[:conflict.head()]):
            for c in chunk_list:
                if l.rstrip() == c['identifier']:
                    identifier = c['identifier']
                    break

        if not identifier:
            return

        for c in chunk_list:
            if c['identifier'] == identifier:
                c['score'] += 1

    @staticmethod
    def _score_chunks_by_addition(conflict, chunk_list):
        # Try to find the conflicting code by comparing the remote portion of
        # the conflict with the added code in each git chunk. The more lines
        # that match, the better the score.
        for chunk in chunk_list:
            for cl in chunk['chunk']:
                if not cl.startswith('+'):
                    continue
                for l in conflict.remote_conflict:
                    if l == cl[1:]:
                        chunk['score'] += 1

    @staticmethod
    def _score_chunks_by_subtraction(conflict, chunk_list):
        # Try to find the conflicting code by comparing the local portion of
        # the conflict with the removed code in each git chunk. The more lines
        # that match, the better the score.
        for chunk in chunk_list:
            for cl in chunk['chunk']:
                if not cl.startswith('-'):
                    continue
                for l in conflict.head_conflict:
                    if l == cl[1:]:
                        chunk['score'] += 1

    def blame_remote(self, conflict):
        """Fetch the git blame output for the remote portion of the conflict.

        Args:
            conflict: The Conflict object to assign blame.

        Returns:
            String containing the git blame output for the conflict's HEAD text.
        """
        diff = self._git.commit_diff(conflict.sha, self._path)
        chunk_list = self._get_diff_chunks(diff)

        # We have to find the chunk in the diff which caused the conflict.
        # This will give us the line number of the change which we can use to
        # narrow down the blame range to the relevant bit.
        if len(chunk_list) == 1:
            # Only one chunk means this is the portion causing the conflict.
            results = chunk_list
        else:
            # This is a bit tricky since there's no sure way to map the local
            # conflict into a diff chunk. For now we'll try a few methods to
            # find the right snippet of code. The chunks with the highest
            # scores (ties are allowed) get displayed to the user.
            self._score_chunks_by_identifier(conflict, chunk_list)
            self._score_chunks_by_addition(conflict, chunk_list)
            self._score_chunks_by_subtraction(conflict, chunk_list)

            results = []
            for c in chunk_list:
                if c['score'] > 0:
                    results.append(c)

        if not results:
            return 'Could not map the local conflict to remote blame.'

        results = sorted(results, key=lambda x: x['score'], reverse=True)
        max_score = results[0]['score']

        ret = ''
        blame = self._git.blame(self._path, f'{conflict.sha}^').splitlines()
        for i, c in enumerate(results):
            if c['score'] < max_score:
                break

            ret += f'>>>>> Possible result {i}, score={c["score"]}\n'
            ret += '-- diff\n'
            ret += '\n'.join(c['chunk'])
            ret += '\n'
            ret += '-- blame\n'
            c_start = max(0, c['old_line'])
            c_end = min(len(blame), c['old_line'] + c['old_num'])
            ret += '\n'.join(blame[c_start:c_end])
            ret += '\n'

        return ret

    def compare_commits(self, conflict):
        head_blame = self.blame_head(conflict)
        remote_blame = self.blame_remote(conflict)
        commits = defaultdict(lambda: {'head': None, 'remote': None})

        for l in head_blame.splitlines():
            commit = Commit.from_blame_line(l)
            if not commit:
                continue
            commits[(commit._date_authored, commit._author)]['head'] = commit._sha

        for l in remote_blame.splitlines():
            commit = Commit.from_blame_line(l)
            if not commit:
                continue
            commits[(commit._date_authored, commit._author)]['remote'] = commit._sha

        ret = f'{"Author Date".ljust(40)}{"Author".ljust(40)}'
        ret += f'{"Local SHA".ljust(20)}{"Remote SHA".ljust(20)}\n'
        for k in sorted(commits.keys()):
            v = commits[k]
            ret += f'{str(k[0]).ljust(40)}{k[1].ljust(40)}'
            if v['head']:
                ret += f'{v["head"].ljust(20)}'
            else:
                ret += f'{"<missing>".ljust(20)}'
            if v['remote']:
                ret += f'{v["remote"].ljust(20)}'
            else:
                ret += f'{"<missing>".ljust(20)}'
            ret += '\n'

        return ret
