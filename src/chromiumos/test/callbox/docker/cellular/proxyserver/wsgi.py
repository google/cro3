# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""CallboxManager WSGI app."""

import logging

from cellular.proxyserver.flask_app import app


gunicorn_logger = logging.getLogger("gunicorn.error")
app.logger.handlers = gunicorn_logger.handlers
app.logger.setLevel(gunicorn_logger.level)

if gunicorn_logger.level >= logging.DEBUG:
    app.config["DEBUG"] = True

if __name__ == "__main__":
    app.run()
