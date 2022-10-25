# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

include $(TOPDIR)/rules.mk

PKG_NAME:=cros-send-management-frame
PKG_VERSION:=1.0.0
PKG_RELEASE:=1
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)/$(PKG_VERSION)

include $(INCLUDE_DIR)/package.mk

# Define package information.
define Package/cros-send-management-frame
	SECTION:=utils
	CATEGORY:=Utilities
	TITLE:=cros-send-management-frame
	DEPENDS:=+libnl-tiny +libpcap
endef
define Package/cros-send-management-frame/description
	Userspace helper which sends management frames via nl80211. This
	can be used to inject frames used for regulatory testing, for example
	spectrum management frames.
endef

# Prepare build directory and copy src into it.
define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	$(CP) ./src/* $(PKG_BUILD_DIR)/
endef

# Compile build using its local Makefile.
define Build/Compile
	$(MAKE) -C $(PKG_BUILD_DIR) \
		CC="$(TARGET_CC)" \
		CFLAGS="$(TARGET_CFLAGS)" \
		LDFLAGS="$(TARGET_LDFLAGS)"
endef

# Instructions on how to install the compiled build.
define Package/cros-send-management-frame/install
	$(INSTALL_DIR) $(1)/bin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/send_management_frame $(1)/bin/
endef

$(eval $(call BuildPackage,cros-send-management-frame))
