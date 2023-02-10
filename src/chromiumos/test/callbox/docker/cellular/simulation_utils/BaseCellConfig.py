# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides base configuration for callbox cells."""

# pylint: disable=banned-string-format-function
# pylint: disable=docstring-leading-whitespace, docstring-section-newline
# pylint: disable=docstring-trailing-quotes, docstring-second-line-blank
# pylint: disable=attribute-defined-outside-init


class BaseCellConfig:
    """Base cell configuration class.

    Attributes:
      output_power: a float indicating the required signal level at the
          instrument's output.
      input_power: a float indicating the required signal level at the
          instrument's input.
    """

    # Configuration dictionary keys
    PARAM_UL_PW = "pul"
    PARAM_DL_PW = "pdl"

    def __init__(self, log):
        """Initialize the base station config by setting all its
            parameters to None.
        Args:
            log: logger object.
        """
        self.log = log
        self.output_power = None
        self.input_power = None
        self.band = None

    def incorporate(self, new_config):
        """Incorporates a different configuration by replacing the current
            values with the new ones for all the parameters different to None.
        Args:
            new_config: 5G cell configuration object.
        """
        for attr, value in vars(new_config).items():
            if value is not None and hasattr(self, attr):
                setattr(self, attr, value)
