#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a utility script for parsing the repo manifest used by gerrit.el"""

import argparse
import pathlib
import subprocess
import sys
import xml.parsers.expat as xml


def parse_manifest_projects_to_lisp_alist(repo_root_path):
    """Parse repo manifest to Lisp alist.

    Any project without a dest-branch attribute is skipped.

    Args:
        repo_root_path: The path to a repo root.

    Returns:
        Lisp readable alist with elements of the form
        ((name . dest-branch) . path)

    Raises:
        CalledProcessError: The repo tool threw an error getting the manifest.
        ExpatError: An error occured when attempting to parse.
    """

    assoc_list_entries = []

    def _project_elem_handler(name, attrs):
        """XML element handler collecting project elements to form a Lisp alist.

        Args:
            name: The name of the handled xml element.
            attrs: A dictionary of the handled xml element's attributes.
        """
        if name == "project":
            project_name = attrs["name"]
            project_path = attrs.get("path", project_name)
            dest_branch = attrs.get("dest-branch")
            if not dest_branch:
                # We skip anything without a dest-branch
                return
            # We don't want the refs/heads/ prefix of dest-branch
            dest_branch = dest_branch.replace("refs/heads/", "")

            key = '("{}" . "{}")'.format(project_name, dest_branch)
            value = '"{}"'.format(project_path)

            assoc_list_entries.append("({} . {})".format(key, value))

    p = xml.ParserCreate()
    p.StartElementHandler = _project_elem_handler

    repo_cmd = ["repo", "--no-pager", "manifest"]
    repo_cmd_result = subprocess.run(
        repo_cmd,
        cwd=repo_root_path.expanduser().resolve(),
        capture_output=True,
        check=True,
    )
    p.Parse(repo_cmd_result.stdout)
    return "({})".format("".join(assoc_list_entries))


def main(argv):
    """main."""
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        "repo_root_path", type=pathlib.Path, help="System path to repo root."
    )
    args = arg_parser.parse_args(argv)

    try:
        print(parse_manifest_projects_to_lisp_alist(args.repo_root_path))
        return 0

    except xml.ExpatError as err:
        print("XML Parsing Error:", err)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
