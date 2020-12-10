#!/usr/bin/env python3

# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import stat
import tempfile
import unittest

from coil_urls import fix_line
from coil_urls import find_files
from coil_urls import fix_file


class TestRegex(unittest.TestCase):

    def test_url_only(self):
        self.assertEqual(fix_line(
            'https://chromium.googlesource.com/chromiumos/docs/+/master/developer_guide.md'),
            'https://chromium.googlesource.com/chromiumos/docs/+/HEAD/developer_guide.md')

    def test_url_with_ref(self):
        self.assertEqual(fix_line(
            'https://chromium.googlesource.com/chromiumos/docs/+/refs/heads/master/developer_guide.md'),
            'https://chromium.googlesource.com/chromiumos/docs/+/HEAD/developer_guide.md')

    def test_text_and_url(self):
        self.assertEqual(fix_line(
            'Some text https://chromium.googlesource.com/chromiumos/docs/+/master/developer_guide.md after'),
            'Some text https://chromium.googlesource.com/chromiumos/docs/+/HEAD/developer_guide.md after')

    def test_multiple_urls(self):
        self.assertEqual(fix_line(
            'https://chromium.googlesource.com/chromiumos/docs/+/master/developer_guide.md'
            ' and https://chromium.googlesource.com/chromiumos/docs/+/master/developer_guide.md'),
            'https://chromium.googlesource.com/chromiumos/docs/+/HEAD/developer_guide.md'
            ' and https://chromium.googlesource.com/chromiumos/docs/+/HEAD/developer_guide.md')

    def test_no_url(self):
        self.assertEqual(fix_line(
            'Some text without a URL.'),
            'Some text without a URL.')

    def test_github_url(self):
        self.assertEqual(fix_line(
            'https://github.com/google/googletest/blob/master/googlemock/docs/cook_book.md#delegating-calls-to-a-parent-class'),
            'https://github.com/google/googletest/blob/HEAD/googlemock/docs/cook_book.md#delegating-calls-to-a-parent-class')

    def test_chromium_source_url(self):
        self.assertEqual(fix_line(
            'https://source.chromium.org/chromium/chromium/src/+/master:chromeos/services/machine_learning/public/cpp/service_connection.h'),
            'https://source.chromium.org/chromium/chromium/src/+/HEAD:chromeos/services/machine_learning/public/cpp/service_connection.h')

    def test_chromium_source_alt_url(self):
        self.assertEqual(fix_line(
            'https://source.chromium.org/chromium/chromium/src/+/refs/heads/master:chromeos/services/machine_learning/public/cpp/service_connection.h'),
            'https://source.chromium.org/chromium/chromium/src/+/HEAD:chromeos/services/machine_learning/public/cpp/service_connection.h')

    def test_android_url(self):
        self.assertEqual(fix_line(
            'https://android.googlesource.com/platform/external/qemu/+/master/docs/ANDROID-QEMUD.TXT#158'),
            'https://android.googlesource.com/platform/external/qemu/+/HEAD/docs/ANDROID-QEMUD.TXT#158')

    def test_chrome_internal_url(self):
        self.assertEqual(fix_line(
            'https://chrome-internal.googlesource.com/foo/bar/+/master/test.h'),
            'https://chrome-internal.googlesource.com/foo/bar/+/HEAD/test.h')


class TestFindFiles(unittest.TestCase):
    def test_find_files(self):
        self.assertEqual(find_files(), ['coil_urls.py', 'coil_urls_test.py'])


class TestFixFile(unittest.TestCase):
    TEST_FILE_TEXT = """
Some text without a URL.
https://chromium.googlesource.com/chromiumos/docs/+/master/developer_guide.md
Some more text.
    """

    TEST_FILE_TEXT_EXPECTED = """
Some text without a URL.
https://chromium.googlesource.com/chromiumos/docs/+/HEAD/developer_guide.md
Some more text.
    """

    TEST_FILE_NOT_UTF8 = b'\x80abc'

    def test_fix_file(self):
        tmp_file = tempfile.NamedTemporaryFile()

        with open(tmp_file.name, 'w') as test_file:
            test_file.write(self.TEST_FILE_TEXT)

        fix_file(tmp_file.name)

        with open(tmp_file.name) as test_file:
            text = test_file.read()
            self.assertEqual(text, self.TEST_FILE_TEXT_EXPECTED)

        tmp_file.close()

    def test_file_not_utf8(self):
        tmp_file = tempfile.NamedTemporaryFile()

        with open(tmp_file.name, 'wb') as test_file:
            test_file.write(self.TEST_FILE_NOT_UTF8)

        fix_file(tmp_file.name)

        with open(tmp_file.name, 'rb') as test_file:
            text = test_file.read()
            self.assertEqual(text, self.TEST_FILE_NOT_UTF8)

        tmp_file.close()

    def test_metadata_not_changed(self):
        tmp_file = tempfile.NamedTemporaryFile()

        with open(tmp_file.name, 'w') as test_file:
            test_file.write(self.TEST_FILE_TEXT)
        orig_mode = stat.S_IFREG |\
            stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | \
            stat.S_IRGRP | stat.S_IXGRP | \
            stat.S_IROTH | stat.S_IXOTH
        os.chmod(tmp_file.name, orig_mode)

        fix_file(tmp_file.name)

        # metadata should be preserved
        st = os.stat(tmp_file.name)
        self.assertEqual(orig_mode, st.st_mode)

        tmp_file.close()


if __name__ == '__main__':
    unittest.main()
