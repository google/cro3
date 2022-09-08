# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

FROM python:3.9

# Create and enter venv
RUN python3.9 -m venv ./venv
ENV VIRTUAL_ENV=./venv
ENV PATH=$VIRTUAL_ENV/bin:$PATH

# Install python dependencies into venv
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy project
COPY ./cellular ./cellular

# Run Flask app via Gunicorn WSGI
ENTRYPOINT ["python3", "-m", "gunicorn", "cellular.proxyserver.wsgi:app", "--timeout=250"]
CMD ["--bind=0.0.0.0:5000", "--log-level=error"]
