# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

all: devserver

devserver:
	@echo "Preparing devserver modules."

install:
	mkdir -p "${DESTDIR}/usr/bin"
	mkdir -p "${DESTDIR}/usr/lib/devserver"
	install -m 0755 host/start_devserver "${DESTDIR}/usr/bin"
	install -m 0755 devserver.py "${DESTDIR}/usr/lib/devserver"
	install -m 0644  \
		builder.py \
		autoupdate.py \
		buildutil.py \
		constants.py \
		devserver_util.py \
		downloadable_artifact.py \
		downloader.py \
		gsutil_util.py \
		"${DESTDIR}/usr/lib/devserver"

	install -m 0755 stateful_update "${DESTDIR}/usr/bin"

	# Data directory for the devserver.
	mkdir -m0777 -p "${DESTDIR}/var/lib/devserver"
	mkdir -m0777 -p "${DESTDIR}/var/lib/devserver/static"
	mkdir -m0777 -p "${DESTDIR}/var/lib/devserver/static/cache"

.PHONY: all devserver install
