# -*- coding: utf-8 -*-
"""Class to manage saving the state of the new_variant process

Copyright 2020 The Chromium OS Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
"""

from __future__ import print_function
import os
# pylint: disable=import-error
# False positive from pylint; python is perfectly capable of importing yaml
import yaml
# pylint: enable=import-error


class variant_status(yaml.YAMLObject):
    """Class to manage saving the state of the new_variant process

    When creating a new variant of a base board, there are several scripts that
    run, possibly at different times. We need to keep track of some basic data
    about the new variant that's being created, where we are in the overall
    process, and information like the CL number or Change-Id for all of the
    different CLs. This class provides a way to save all of that data into a
    yaml file in the user's home directory.
    """
    yaml_loader = yaml.SafeLoader
    yaml_tag = u'!variant_status'
    def __init__(self, yaml_name='.new_variant.yaml', soc_type='qs'):
        """Initialize the class

        yaml_name will be the full path and name of the yaml file in the
        current user's home directory.

        Args:
            yaml_name: Name of the yaml file, defaults to 'new_variant.yaml'
            soc_type: SoC Type, defaults to "qs"
        """
        self.yaml_file = os.path.expanduser(os.path.join('~', yaml_name))
        self.board = None
        self.variant = None
        self.soctype = soc_type
        self.bug = None
        self.step = None


    def __repr__(self):
        return '{!s}(board={!r}, variant={!r}, soctype={!r}, bug={!r}, ' \
            'state={!r})'.format(self.__class__.__name__, self.board,
                                 self.variant, self.soctype, self.bug,
                                 self.step)


    def save(self):
        """Save class data into the yaml file"""
        with open(self.yaml_file, 'w') as stream:
            yaml.dump(self, stream, default_flow_style=False)


    def load(self):
        """Load data structure from the yaml file"""
        with open(self.yaml_file, 'r') as stream:
            obj = yaml.safe_load(stream)
            # Copy everything from new object into self
            self.__dict__.update(obj.__dict__)


    def rm(self):
        """Delete the yaml file"""
        os.remove(self.yaml_file)


    def yaml_file_exists(self):
        """Determine if the yaml file exists

        Returns:
            True if the file exists, False otherwise
        """
        return os.path.exists(self.yaml_file) and os.path.isfile(self.yaml_file)
