# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

all: devserver

devserver:
	@echo "Preparing devserver modules."

install:
	mkdir -p "${DESTDIR}/usr/bin"
	mkdir -p "${DESTDIR}/usr/lib/devserver"
	mkdir -p "${DESTDIR}/usr/lib/devserver/dut-scripts"
	install -m 0755 host/start_devserver host/strip_package "${DESTDIR}/usr/bin"
	install -m 0755 devserver.py strip_package.py "${DESTDIR}/usr/lib/devserver"
	install -m 0644  \
		autoupdate.py \
		builder.py \
		cherrypy_ext.py \
		health_checker.py \
		nebraska/nebraska.py \
		setup_chromite.py \
		"${DESTDIR}/usr/lib/devserver"

  # The dut-scripts content is only used when installed on Moblab.
  # Mode 0644 for these files because they're for serving to DUTs
  # over HTTP, not for local execution.
	install -m 0644 quick-provision/quick-provision \
		"${DESTDIR}/usr/lib/devserver/dut-scripts"

.PHONY: all devserver install
