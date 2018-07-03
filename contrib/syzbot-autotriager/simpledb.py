# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Wrapper around python-dataset."""

from __future__ import print_function

import dataset


class SimpleDB(object):
    """SimpleDB is a wrapper for accessing and modifying SQLite caches."""
    def __init__(self, filename):
        self.filename = filename
        self.db = dataset.connect('sqlite:///%s' % (filename))
        self.table = self.db[filename.split('.')[0]]

    def insert(self, **kwargs):
        """Insert values into the table."""
        self.table.insert(kwargs)

    def begin(self):
        """Initiate a transaction on the db."""
        self.db.begin()

    def commit(self):
        """Commit the changes into the db."""
        self.db.commit()

    def find(self, **kwargs):
        """Returns all matching rows in the table.

        find(a="b") returns all rows in the table with
        value 'b' for column a.
        """
        return self.table.find(**kwargs)

    def find_one(self, **kwargs):
        """Returns one row in the table.

        find_one(a="b") returns one row in the table with
        value 'b' in column a.
        """
        return self.table.find_one(**kwargs)

    def all(self):
        """Returns all records in the table."""
        return self.table.all()

    def distinct(self, column):
        """Returns all distinct values in |column|."""
        return self.table.distinct(column)

    def count(self):
        """Returns the number of rows in the table."""
        return self.table.count()
