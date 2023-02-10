# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides minimum required logging functionality to support callbox libraries."""

import logging


class LoggerAdapter(logging.LoggerAdapter):
    """A wrapper that provides logging functionality for callbox libraries."""

    def __init__(self, wrapper):
        self._wrapper = wrapper if wrapper else lambda msg: msg
        logger = logging.getLogger("gunicorn.error")
        super().__init__(logger, {})

    def process(self, msg, kwargs):
        return self._wrapper(msg), kwargs


def create_logger(wrapper=None):
    """Returns a logger whose messages are wrapped with the given wrapper.

    Args:
        wrapper: An anonymous function of the type fun(msg: str) -> str
    """
    return LoggerAdapter(wrapper)


def create_tagged_trace_logger(tag=""):
    """Returns a logger that tags each line with a given prefix.

    Args:
        tag: the tag to prefix log messages with.
    """
    return create_logger(lambda msg: f"{tag} {msg}")
