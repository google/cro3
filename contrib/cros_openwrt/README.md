# How to build a test OpenWrt image

## Install system dependencies
See https://openwrt.org/docs/guide-user/additional-software/imagebuilder#prerequisites
for instructions.

## Build the custom image
1. Find your router in the [list of supported devices](https://openwrt.org/supported_devices)
([table lookup](https://openwrt.org/toh/start)).
2. Open the data page associated with your router from the supported devices
table (e.g. https://openwrt.org/toh/hwdata/ubiquiti/ubiquiti_unifi_6_lite).
3. Navigate to the directory of where the "Firmware OpenWrt Upgrade URL" is
located (e.g. from `https://downloads.openwrt.org/releases/21.02.2/targets/ramips/mt7621/openwrt-21.02.2-ramips-mt7621-ubnt_unifi-6-lite-squashfs-sysupgrade.bin` go to https://downloads.openwrt.org/releases/21.02.2/targets/ramips/mt7621).
4. Scroll down to the bottom of the page to the "Supplementary Files" section
and copy the URL (you do not need to download it now) to the image builder
archive, which should match `openwrt-imagebuilder-*.tar.xz`
(e.g. https://downloads.openwrt.org/releases/21.02.2/targets/ramips/mt7621/openwrt-imagebuilder-21.02.2-ramips-mt7621.Linux-x86_64.tar.xz).
5. Run the build script with just the image builder URL to download and unpack
the builder, as well as print its available build profiles:

Example:
```bash
$ bash ./build_cros_openwrt_os_image.sh https://downloads.openwrt.org/releases/21.02.2/targets/ramips/mt7621/openwrt-imagebuilder-21.02.2-ramips-mt7621.Linux-x86_64.tar.xz
```

7. Choose the correct build profile based on your device. You can find it in
your devices "Firmware OpenWrt Upgrade URL" as well (e.g. `ubnt_unifi-6-lite`)
8. Run the build script again with the same image builder URL and the build
profile that you selected:

Example:
```bash
$ bash ./build_cros_openwrt_os_image.sh https://downloads.openwrt.org/releases/21.02.2/targets/ramips/mt7621/openwrt-imagebuilder-21.02.2-ramips-mt7621.Linux-x86_64.tar.xz ubnt_unifi-6-lite
```

9. Access your newly built image at `/tmp/openwrt_img_building/bin/`. Depending
on the build profile for the device, it may create multiple images. See the
device-specific installation documentation in order to determine which image you
should use.


## Install the custom image
Custom-built images are installed the same way as normal OpenWrt images
([offical docs](https://openwrt.org/docs/guide-quick-start/factory_installation)).

### On a device not yet running OpenWrt
Follow the instructions on the device's info page on the OpenWrt wiki. Just be
sure to use the corresponding custom image binary instead of one downloaded
from the OpenWrt image repository.

### On a device already running OpenWrt
Follow the instructions on the device's info page on the OpenWrt wiki, but in
general it should be the following steps:
1. Use `scp` to copy the custom image (should have the `.bin` file extension) to
the router's `/tmp` directory.
2. Run `sysupgrade /tmp/your_custom_image.bin`
3. Wait a few minutes for the image to be installed and for the device to reboot.


## Accessing the router after installing the custom OpenWrt image
The CROS customizations will disable the router's DHCP server and not turn on
any wireless networks, but will configure the device to connect to act as a DHCP
client and thus allow it to be accessed via ssh through other networks it is
physically connected to (such as a lab network).

As long as you know the IP address of the router and can connect to the network
the router is connected to, you can ssh into the router as the `root` user and
the regular cros [testing_rsa](../../../../../chromeos-admin/puppet/modules/profiles/files/user-common/ssh/testing_rsa)
private key. This is the same way DUTs and Gale routers are accessed.

If you do not know the IP address of the router, you will need to obtain it by
checking the network the router is connected to and identify the router using
its MAC address. It is recommended configure the parent network to statically
assign the router a consistent IP based on its MAC address for long-term usage.
