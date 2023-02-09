#!/usr/bin/env python3
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fixes common URLs for COIL.
"""
import argparse
import logging
import re
import shutil
import subprocess
import sys
import tempfile


class Pattern:
    def __init__(self, match_pattern, repl_pattern):
        self.match_pattern = match_pattern
        self.repl_pattern = repl_pattern


DEFAULT_REGEX_PATTERN = r"({DOMAIN}[^\s]*\/\+\/)(master)"
ALT_REGEX_PATTERN = r"({DOMAIN}[^\s]*\/\+\/)(refs\/heads\/master)"

GOOGLESOURCE = "googlesource.com"
SOURCE_CHROMIUM_ORG = "source.chromium.org"

GOOGLESOURCE_REGEX = DEFAULT_REGEX_PATTERN.format(DOMAIN=GOOGLESOURCE)
GOOGLESOURCE_REGEX_ALT = ALT_REGEX_PATTERN.format(DOMAIN=GOOGLESOURCE)
CHROMIUM_SOURCE_REGEX = DEFAULT_REGEX_PATTERN.format(DOMAIN=SOURCE_CHROMIUM_ORG)
CHROMIUM_SOURCE_REGEX_ALT = ALT_REGEX_PATTERN.format(DOMAIN=SOURCE_CHROMIUM_ORG)
GITHUB_REGEX = r"(github.com[^\s]*\/)(master)"
DEFAULT_REPL_PATTERN = r"\1HEAD"

DOMAINS = [
    GOOGLESOURCE_REGEX,
    GOOGLESOURCE_REGEX_ALT,
    CHROMIUM_SOURCE_REGEX,
    CHROMIUM_SOURCE_REGEX_ALT,
    GITHUB_REGEX,
]

PATTERNS = [
    Pattern(match_pattern=x, repl_pattern=DEFAULT_REPL_PATTERN) for x in DOMAINS
]


def fix_line(text: str):
    # iterate through patterns. if line is changed, return
    for pattern in PATTERNS:
        new_str, count = re.subn(
            pattern.match_pattern, pattern.repl_pattern, text
        )
        if count > 0:
            return new_str

    return text


def fix_file(file: str):
    try:
        with tempfile.NamedTemporaryFile() as tmp_file:
            logging.debug("created temp file: %s", tmp_file.name)

            # replace line-by-line
            with open(file) as orig_file:
                for line in orig_file:
                    newline = fix_line(line)

                    # write newline to temp file
                    tmp_file.write(newline.encode())

            # replace orig with temp file
            tmp_file.flush()
            shutil.copyfile(tmp_file.name, file)
    except UnicodeDecodeError:
        # skip any files that aren't utf8
        pass


def is_git_dir():
    cmd = ["git", "rev-parse", "--git-dir"]
    logging.debug('Running command: "%s"', " ".join(cmd))
    ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return ret.returncode == 0


def find_files():
    git_cmd = ["git", "grep", "--name-only"]
    grep_cmd = ["grep", "-r", "--files-with-matches"]

    if is_git_dir():
        cmd = git_cmd
    else:
        cmd = grep_cmd

    cmd.append("master")
    logging.debug('Running command: "%s"', " ".join(cmd))
    ret = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
    return ret.stdout.decode().splitlines()


def main():
    parser = argparse.ArgumentParser()

    log_level_choices = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    parser.add_argument(
        "--log_level", "-l", choices=log_level_choices, default="INFO"
    )

    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)

    for file_name in find_files():
        fix_file(file_name)

    sys.exit(0)


if __name__ == "__main__":
    sys.exit(main())
