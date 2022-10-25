# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

CFLAGS += -Wall -Wextra -Werror -g
CFLAGS += -Wno-unused-parameter
CFLAGS += -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE -D_LARGEFILE64_SOURCE

PKG_CONFIG ?= pkg-config
PC_LIBS := $(shell $(PKG_CONFIG) )
PC_CFLAGS := $(shell $(PKG_CONFIG) --cflags $(PC_DEPS))

CFLAGS += $(PC_CFLAGS)
LDLIBS += $(PC_LIBS)

all: send_management_frame

send_management_frame: send_management_frame.o
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^ $(LDLIBS) -lpcap
