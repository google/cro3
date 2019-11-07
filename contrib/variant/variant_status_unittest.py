#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit test for the variant_status class

To avoid disrupting any work in progress, this unit test will set the name
of the yaml file to variant_status_unittest.yaml

Copyright 2019 The Chromium OS Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
"""

from __future__ import print_function
import unittest
import variant_status


class TestVariantStatus(unittest.TestCase):
    """Unit test for the variant_status class"""
    def setUp(self):
        """Set up for a test

        Use a different yaml filename so that we don't stomp on any work in
        progress, and remove the yaml file if it exists.
        """
        self.status = variant_status.variant_status('variant_status_unittest.yaml')
        if self.status.yaml_file_exists():
            self.status.rm()


    def tearDown(self):
        """Clean up after the test

        If the yaml file exists, remove it.
        """
        if self.status.yaml_file_exists():
            self.status.rm()
        self.status = None


    def test_given_file_does_not_exist_then_file_exists_returns_false(self):
        """Check that the file doesn't exist if we haven't created it."""
        self.assertFalse(self.status.yaml_file_exists())

    def test_when_save_file_then_file_exists_returns_true(self):
        """After saving the file, yaml_file_exists() should confirm it exists"""
        self.status.save()
        self.assertTrue(self.status.yaml_file_exists())

    def test_when_save_file_with_new_data_then_new_data_is_correct(self):
        """Create file with data, change and save, then load into new object"""
        self.status.board = 'hatch'
        self.status.variant = 'sushi'
        self.status.bug = 'b:12345'
        self.status.stage = 'initial'
        self.status.save()

        self.status.bug = 'FooBar'
        self.status.save()

        new_status = variant_status.variant_status('variant_status_unittest.yaml')
        new_status.load()
        self.assertTrue(new_status.bug == 'FooBar')

    def test_when_add_new_field_to_file_then_field_is_saved_and_loaded(self):
        """Create a file, add a new field, and ensure it is saved and loaded"""
        self.status.board = 'hatch'
        self.status.variant = 'sushi'
        self.status.bug = 'b:12345'
        self.status.stage = 'initial'
        self.status.save()

        self.status.packages = 'chromeos-ec'
        self.status.save()

        new_status = variant_status.variant_status('variant_status_unittest.yaml')
        new_status.load()
        self.assertTrue(new_status.packages == 'chromeos-ec')

    def test_when_field_is_list_then_list_is_loaded_correctly(self):
        """If we assign a list to a field, we can load the list correctly"""
        self.status.workon = ['item1', 'item2']
        self.status.save()

        new_status = variant_status.variant_status('variant_status_unittest.yaml')
        new_status.load()
        self.assertTrue(new_status.workon[0] == 'item1')
        self.assertTrue(new_status.workon[1] == 'item2')

    def test_when_field_is_empty_list_then_append_to_list_is_still_correct(self):
        """If the list is empty, appending to it works correctly"""
        self.status.emerge.append('chromeos-ec')
        self.status.emerge.append('chromeos-config-bsp')
        self.status.save()

        new_status = variant_status.variant_status('variant_status_unittest.yaml')
        new_status.load()

        self.assertTrue(new_status.emerge[0] == 'chromeos-ec')
        self.assertTrue(new_status.emerge[1] == 'chromeos-config-bsp')

if __name__ == '__main__':
    unittest.main()
