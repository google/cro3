#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a utility script for parsing repo manifest files used by gerrit.el"""

import xml.parsers.expat as xml
import sys
import argparse
import pathlib

def parse_manifest_projects_to_lisp_alist(manifest_path):
    """Parse manifest xml to Lisp alist.

    Any project without a dest-branch attribute is skipped.

    Args:
        manifest_path: The path to a trusted repo manifest file to parse project elements.

    Returns:
        Lisp readable alist with elements of the form ((name . dest-branch) . path)

    Raises:
        ExpatError: An error occured when attempting to parse.
    """

    assoc_list_entries = []

    def _project_elem_handler(name, attrs):
        """XML element handler collecting project elements to form a Lisp alist.

        Args:
            name: The name of the handled xml element.
            attrs: A dictionary of the handled xml element's attributes.
        """
        if name == 'project':
            project_path = attrs['path']
            project_name = attrs['name']
            dest_branch = attrs['dest-branch'] if 'dest-branch' in attrs else None
            if not dest_branch:
                # We skip anything without a dest-branch
                return
            # We don't want the refs/heads/ prefix of dest-branch
            dest_branch = dest_branch.replace('refs/heads/', '')

            key = '("{}" . "{}")'.format(project_name, dest_branch)
            value = '"{}"'.format(project_path)

            assoc_list_entries.append('({} . {})'.format(key, value))

    p = xml.ParserCreate()
    p.StartElementHandler = _project_elem_handler
    with open(manifest_path, 'rb') as manifest_fd:
        p.ParseFile(manifest_fd)
        return '({})'.format(''.join(assoc_list_entries))


def main(argv):
    """main."""
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('repo_manifest_path',
                            type=pathlib.Path,
                            help='System path to repo manifest xml file.')
    args = arg_parser.parse_args(argv)

    try:
        print(parse_manifest_projects_to_lisp_alist(args.repo_manifest_path))
        return 0

    except xml.ExpatError as err:
        print('XML Parsing Error:', err)
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
