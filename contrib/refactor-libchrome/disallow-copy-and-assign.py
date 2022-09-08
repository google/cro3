#!/usr/bin/env python
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Usage: ag DISALLOW_COPY_AND_ASSIGN -l | xargs -n 1 python[23] ./disallow-copy-and-assign.py

Please note, this script doesn't guanrantee all usages are correctly replaced.
Result must be checked by humans.
Known issues:
  1. It may put in the middle of inlined complex constructor function body.
  2. It may failed to locate constructor and put the line after public: if
  constructor is complex (especially member initialization).
  3. It may failed to locate public: and not altering the file.
  4. It may put the code into protected or private if the original code has a
  protected or private constructor.

This script doesn't format code, please run:
  src/repohooks/clang-format.py --fix . --working
to format code with clang-foramt.

Also the script doesn't delete empty lines or empty priavte: section.
Scripts like:
  git diff-tree -r HEAD | awk '{print $6;}' | xargs  perl -0 -i -pe 's/ *private:\n*}/}/g'
  git diff-tree -r HEAD | awk '{print $6;}' | xargs  perl -0 -i -pe 's/\n\n};/\n};/g'
are recommend AFTER git commit is made (and you can amend commit later).

You can use the following validity check script to help locate known issue (1):
  git diff m/master | egrep -o '^[+-]   +([A-Za-z0-9]+\(|DISALLOW_COPY_AND_ASSIGN).*'
The script helps you quickly filter only diffs that are not with exact 2-space
indent. And you can look at if the result is in pairs.
"""

import re
import sys


def main():
    content = open(sys.argv[1], 'r').read()

    while True:
        found = re.search(r'^ *DISALLOW_COPY_AND_ASSIGN\(([^)]*)\);', content,
                          re.MULTILINE)
        if not found:
            break
        classname = found.group(1)
        found_constructors = list(
            re.compile(
                '^ *(explicit )?' + classname + '\(([^;{]*;|[^;{]*{[^}]*})$',
                re.MULTILINE).finditer(content, 0, found.start()))
        if found_constructors:
            # Pick the last constructor.
            insertion_point = found_constructors[-1].end()
        else:
            # If no constructors are found, look for public:.
            insertion_point = list(
                re.compile('class ' + classname + r' .*{[ \n]*public:\n',
                           re.MULTILINE).finditer(content, 0,
                                                  found.start()))[-1].end()
        content = ('%(prefix)s' + '%(name)s(const %(name)s&) = delete;\n' +
                   '%(name)s& operator=(const %(name)s&) = delete;\n'
                   '%(middle)s%(suffix)s') % {
                       'prefix': content[0:insertion_point + 1],
                       'name': classname,
                       'middle': content[insertion_point:found.start()],
                       'suffix': content[found.end() + 1:],
                   }
    open(sys.argv[1], 'w').write(content)


if __name__ == '__main__':
    main()
