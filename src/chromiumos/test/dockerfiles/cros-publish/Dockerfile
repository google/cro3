# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

FROM python:3.8-slim-buster AS build

# Install python packages
# Due to the way builds happen in the bots, the requirements.txt has a
# different checksum (as the file path changes per build), thus breaks the
# cache. This way of declaring allows the cloudbuild cache to be carried
# between builds/boards.
# To update this list, add the new dep to requirements.in, regenerate the
# requirements_py3.txt, then manually copy in the dep to the list below,
# including the \n\.
RUN echo "\
chardet==3.0.4\n\
grpcio==1.31.0\n\
protobuf==3.18.0\n\
requests==2.26.0\n\
selenium==2.37.2\n\
six==1.15.0\n\
urllib3==1.26.7\n\
google.cloud\n\
google.cloud.pubsub\n\
google.cloud.storage\n\
" > requirements_py3.txt
RUN pip3 install -r requirements_py3.txt

COPY gcs-publish /usr/bin/gcs-publish
COPY tko-publish /usr/bin/tko-publish
COPY rdb-publish /usr/bin/rdb-publish
COPY cpcon-publish /usr/bin/cpcon-publish

COPY rdb /usr/bin/rdb
COPY result_adapter /usr/bin/result_adapter

COPY result_adapter_cipd_metadata.json /tmp/rdb-publish/result_adapter_cipd_metadata.json
COPY rdb_cipd_metadata.json /tmp/rdb-publish/rdb_cipd_metadata.json

COPY autotest/ /usr/local/autotest
COPY contrib/ /usr/local/autotest/contrib/