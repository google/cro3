#!/usr/bin/env python3

# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=missing-docstring

import unittest
import pathlib

from mock import call
from mock import patch

from chromium_metadata import chromium_metadata
from chromium_metadata import create_metadata_files
from chromium_metadata import extract_owners
from chromium_metadata import find_owners_files

GIT_REPO_DIR = pathlib.Path('/mnt/host/source/src/platform/dev')
TEST_DATA_DIR = pathlib.Path('./test_data')
OWNERS_FILE1 = TEST_DATA_DIR.joinpath('OWNERS')
OWNERS_FILE2 = TEST_DATA_DIR.joinpath('component/OWNERS')


class TestExtractOwners(unittest.TestCase):
    def test_extract_owners(self):
        self.assertEqual(extract_owners(TEST_DATA_DIR.joinpath('OWNERS')),
                         ['tomhughes@chromium.org'])


class TestFindOwnersFiles(unittest.TestCase):
    def test_find_owners_files(self):
        self.assertEqual(find_owners_files(TEST_DATA_DIR),
                         [OWNERS_FILE1,
                          OWNERS_FILE2])


class TestCreateMetadataFiles(unittest.TestCase):
    @patch('chromium_metadata.create_cl')
    def test_create_metadata_files(self, create_cl_mock):
        create_metadata_files(TEST_DATA_DIR)
        expected = [
            call(sub_dir=pathlib.Path('.'),
                 git_repo=TEST_DATA_DIR,
                 reviewers=['tomhughes@chromium.org']),
            call(sub_dir=pathlib.Path('component'),
                 git_repo=TEST_DATA_DIR,
                 reviewers=['adlr@chromium.org',
                            'tomhughes@chromium.org'])
        ]
        create_cl_mock.assert_has_calls(expected)
        self.assertEqual(create_cl_mock.call_count, len(expected))


class TestChromiumMetadata(unittest.TestCase):
    @patch('chromium_metadata.create_metadata_files')
    def test_chromium_metadata(self, create_metadata_files_mock):
        chromium_metadata()
        create_metadata_files_mock.assert_called_with(GIT_REPO_DIR)


if __name__ == '__main__':
    unittest.main()
