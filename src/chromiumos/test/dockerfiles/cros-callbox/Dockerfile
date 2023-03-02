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

# Add ssh keys and configure
RUN mkdir -p /tmp/dldir
RUN mkdir -p ~/.ssh
RUN wget -P /tmp/dldir https://chromium.googlesource.com/chromiumos/chromite/+archive/3045c5df5fb784858cd0e7cd98608a5d7570d842/ssh_keys.tar.gz
RUN tar -xvf /tmp/dldir/ssh_keys.tar.gz -C ~/.ssh
RUN chmod 400 ~/.ssh/testing_rsa

RUN  echo '\n\
Host * \n\
  User root \n\
  StrictHostKeyChecking=no \n\
  IdentityFile %d/.ssh/testing_rsa \n\
  UserKnownHostsFile=/dev/null \n\
'> ~/.ssh/config

# Copy project
COPY ./cellular ./cellular

# Run Flask app via Gunicorn WSGI
ENTRYPOINT ["python3", "-m", "gunicorn", "cellular.proxyserver.wsgi:app", "--timeout=250"]
CMD ["--bind=0.0.0.0:5000", "--log-level=error"]
