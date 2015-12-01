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
		android_build.py \
		artifact_info.py \
		autoupdate.py \
		autoupdate_lib.py \
		build_artifact.py \
		build_util.py \
		builder.py \
		cherrypy_ext.py \
		common_util.py \
		devserver_constants.py \
		downloader.py \
		gsutil_util.py \
		log_util.py \
		retry.py \
		strip_package.py \
		xbuddy.py \
		xbuddy_config.ini\
		"${DESTDIR}/usr/lib/devserver"

	install -m 0755 stateful_update "${DESTDIR}/usr/bin"

	# Data directory for the devserver.
	mkdir -m0777 -p "${DESTDIR}/var/lib/devserver"
	mkdir -m0777 -p "${DESTDIR}/var/lib/devserver/static"
	mkdir -m0777 -p "${DESTDIR}/var/lib/devserver/static/cache"

.PHONY: all devserver install
