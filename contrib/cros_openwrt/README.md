# How to build a test OpenWrt OS image with `cros_openwrt_image_builder`

The `cros_openwrt_image_builder` CLI utility can be used to build test OpenWrt
OS images. It makes use of official OpenWrt sdks to compile custom OpenWrt
packages and then uses official OpenWrt image builders to build the image with
these custom packages and other image modification settings.

OpenWrt images can be built in their entirety from source, but using the
combined approach of the sdk and the image builder ensures that our
built images include only the minimal amount of customizations necessary by only
overriding the specific package IPKs we define. Plus, it's faster.

The `cros_openwrt_image_builder` is designed to allow for building test OpenWrt
OS images for any device already supported by OpenWrt, with minimal effort for
switching between devices and/or OpenWrt versions/snapshots.

This is not guaranteed to work with every OpenWrt version and device, but it
should at least be able to attempt to build the packages and images given
that the provided target has an accessible official sdk and image builder.

Tested with the following devices and OpenWrt versions:
* [Ubiquiti - UniFi 6 Lite](https://openwrt.org/toh/hwdata/ubiquiti/ubiquiti_unifi_6_lite)
  * [21.02.5](https://downloads.openwrt.org/releases/21.02.5/targets/ramips/mt7621/)
  * [22.03.2](https://downloads.openwrt.org/releases/22.03.2/targets/ramips/mt7621/)

## Install system dependencies
See https://openwrt.org/docs/guide-user/additional-software/imagebuilder#prerequisites
for instructions.

You will also need ~3GB of hard drive space for the build files.

## Build & Install cros_openwrt_image_builder
Use the `./install.sh` bash script to build and install
cros_openwrt_image_builder so that it may be run as a regular command,
`cros_openwrt_image_builder`. The built copy will reside at
`./bin/cros_openwrt_image_builder`.

Note: The installation script is meant to be run on your main system, not in a
chroot.

Note: Syncing an updated version of this source repository will not
automatically rebuild an updated version of `cros_openwrt_image_builder`. To
update your local build of `cros_openwrt_image_builder`, simply re-run
`./install.sh` (or `./build.sh`) to rebuild it.

```text
$ $ bash ./install.sh help
Usage: install.sh [options]

Options:
 --dir|-d <path>    Path to directory where cros_openwrt_image_builder is to be
                    installed, which should be in your $PATH
                    (default = '~/lib/depot_tools').
```

## Build the default custom image from a fresh install
1. Find your router in the [list of supported devices](https://openwrt.org/supported_devices)
([table lookup](https://openwrt.org/toh/start)).

2. Open the data page associated with your router from the supported devices
table (e.g. https://openwrt.org/toh/hwdata/ubiquiti/ubiquiti_unifi_6_lite).

3. Make note of the "Firmware OpenWrt Upgrade URL" (e.g. `https://downloads.openwrt.org/releases/22.03.2/targets/ramips/mt7621/openwrt-22.03.2-ramips-mt7621-ubnt_unifi-6-lite-squashfs-sysupgrade.bin
   `).

4. Run `cros_openwrt_image_builder build` and specify `--auto_url` as the
"Firmware OpenWrt Upgrade URL":

```text
$ cros_openwrt_image_builder build --auto_url <Firmware OpenWrt Upgrade URL>
```

Note: This assumes your chroot is installed at `~/chromiumos`. If it isn't, you
need to supply the path to this source directory (`cros_openwrt`) with the
`--src_dir <path_to_cros_openwrt>` flag.

5. When prompted, confirm that the resolved sdk and image builder archive URLs
are for your desired build target, which was parsed from the `--auto_url` param.

6. Wait for the sdk to be downloaded, extracted, and used to build all the
custom packages and their dependencies. This will take a long time (~1hr) the
first time this is run for the sdk. Note: In future runs for the same build
target you can specify the `--use_existing_sdk` flag to not start from scratch,
which is much faster.

7. Once the sdk finishes building the custom packages, the official image
builder is downloaded, extracted, and used to build the custom OpenWrt OS image.
When prompted, choose the correct build profile based on your target device. You
can find it in your devices "Firmware OpenWrt Upgrade URL" as well (e.g.
`ubnt_unifi-6-lite`). You can skip this prompt in future runs if you know the
profile already with the `--image_profile <profile>` flag.

8. Wait for the image builder to build the image (<5m). This will download any
needed official package IPKs. The custom package IPKs build by the local sdk are
included as well, and override any official ones. Any dependency of a custom
package is downloaded if it is not explicitly included (i.e. we only use the
customized packages direct IPKs and not its dependencies which the sdk also
builds).

9. Open the path to the image directory displayed. For convenience, the
directory includes all related image files for local use as well as
a timestamped *.tar.xz archive of these files for easy distribution.

If you want to test a different OpenWrt OS version, simply provide an
`--auto_url` for a different version and repeat the steps starting from step 4.

By default, the working directory (`/tmp/cros_openwrt/` by default) is not
deleted after the command is finished so that it may be used as a reference. To
delete just the intermediary build files, you can run
`cros_openwrt_image_builder clean`. To delete the whole
working directory, including copies of previously built images, you can run
`cros_openwrt_image_builder clean --all`.

Example call for building an image with OpenWrt version `21.02.5` for a
`Ubiquiti - UniFi 6 Lite` router:
```text
$ cros_openwrt_image_builder build --auto_url=https://downloads.openwrt.org/releases/21.02.5/targets/ramips/mt7621/ --image_profile ubnt_unifi-6-lite
```

### Build summary

The built image includes a summary of the build which can be referenced on
the device it is installed on at `/`

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
the router's `/tmp` directory:

```text
$ scp <path_to_image.bin> <host>:/tmp
```

If you get the `ash: /usr/libexec/sftp-server: not found` error when using scp,
add the `-O` flag (newer OpenSSH versions default to use SFTP which OpenWrt
does not support).

```text
$ scp -O <path_to_image.bin> <host>:/tmp
```

3. Run `sysupgrade /tmp/your_custom_image.bin`

4. Wait a few minutes for the image to be installed and for the device to
reboot.

5. Upon reconnecting to the device, you can check the build info of the
installed image at `/etc/cros/build_info.json`:
```text
BusyBox v1.35.0 (2022-10-21 07:56:04 UTC) built-in shell (ash)

  _______                     ________        __
 |       |.-----.-----.-----.|  |  |  |.----.|  |_
 |   -   ||  _  |  -__|     ||  |  |  ||   _||   _|
 |_______||   __|_____|__|__||________||__|  |____|
          |__| W I R E L E S S   F R E E D O M
 -----------------------------------------------------
 OpenWrt 22.03.2, r19803-9a599fee93
 -----------------------------------------------------
root@OpenWrt:~# cat /etc/cros/build_info.json
{
  "BUILD_DATETIME": "2022-10-24T23:14:40-07:00",
  "CROS_IMAGE_BUILDER_VERSION": "1.0.0",
  "CUSTOM_INCLUDED_FILES": {
    "etc/dropbear/authorized_keys": "408f2b0c95706cbf38aa44469204ef87221a9beeb9fff2901b93cbebabf62b2c",
    "etc/uci-defaults/99_cros_customizations.sh": "084d7279edf6267409163789d1637c8f7f23875589673263114371fed7c0239a"
  },
  "CUSTOM_PACKAGES": {
    "cros-send-management-frame_1.0.0-1_mipsel_24kc.ipk": "f658470e5f3da09169dabc0b4097dde6cad5ecccd0ffcda749b873efe2c9229a",
    "hostapd-common_2022-01-16-cff80b4f-1.1_mipsel_24kc.ipk": "084c7c0d3b5a6b91e3a5efd141d4975e4d3497648ce05c52717f46eadeb2ffff",
    "hostapd-utils_2022-01-16-cff80b4f-1.1_mipsel_24kc.ipk": "d2c4d04f857ed0abc81a2a49be1361c9dbb79eb001b4875b90361054e9af7880",
    "wpa-cli_2022-01-16-cff80b4f-1.1_mipsel_24kc.ipk": "89130e15bcf9c87aa7d4b06b6a89e10b884302de692cb193c0d6087e18a45722",
    "wpad-openssl_2022-01-16-cff80b4f-1.1_mipsel_24kc.ipk": "e3ee66e8759f382c78140846edeb62b090633a1b617285b2c5707ce9ca24b674"
  },
  "DISABLED_SERVICES": [
    "wpad",
    "dnsmasq"
  ],
  "EXCLUDED_PACKAGES": [
    "hostapd",
    "hostapd-basic",
    "hostapd-basic-openssl",
    "hostapd-basic-wolfssl",
    "hostapd-mini",
    "hostapd-openssl",
    "hostapd-wolfssl",
    "wpad",
    "wpad-mesh-openssl",
    "wpad-mesh-wolfssl",
    "wpad-basic",
    "wpad-basic-openssl",
    "wpad-basic-wolfssl",
    "wpad-mini",
    "wpad-wolfssl",
    "wpa-supplicant",
    "wpa-supplicant-mesh-openssl",
    "wpa-supplicant-mesh-wolfssl",
    "wpa-supplicant-basic",
    "wpa-supplicant-mini",
    "wpa-supplicant-openssl",
    "wpa-supplicant-p2p",
    "eapol-test",
    "eapol-test-openssl",
    "eapol-test-wolfssl"
  ],
  "EXTRA_IMAGE_NAME": "cros-1.0.0",
  "IMAGE_BUILDER_PROFILE": "ubnt_unifi-6-lite",
  "INCLUDE_PACKAGES": [
    "cros-send-management-frame",
    "hostapd-common",
    "hostapd-utils",
    "wpad-openssl",
    "wpa-cli",
    "kmod-veth",
    "tcpdump",
    "procps-ng-pkill",
    "netperf",
    "iperf",
    "sudo"
  ]
}
```


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


## `cros_openwrt_image_builder`
```text
$ cros_openwrt_image_builder help
Utility for building custom OpenWrt OS images with custom compiled packages

Usage:
  cros_openwrt_image_builder [command]

Available Commands:
  build          Compiles custom OpenWrt packages and builds a custom OpenWrt image.
  build:image    Builds a custom OpenWrt image.
  build:packages Compiles custom OpenWrt packages.
  clean          Deletes temporary files.
  completion     Generate the autocompletion script for the specified shell
  help           Help about any command

Flags:
      --auto_url string                        Download URL to use to auto resolve unset --sdk_url and --image_builder_url values from.
      --chromiumos_src_dir string              Path to local chromiumos source directory. (default "/usr/local/google/home/jaredbennett/chromiumos")
      --disable_auto_sdk_compile_retry         Include to disable the default behavior of retrying the compilation of custom packages once if the first attempt fails. (default true)
      --disable_service stringArray            Services to disable in the built image. (default [wpad,dnsmasq])
      --exclude_package stringArray            Packages to exclude from the built image. (default [hostapd,hostapd-basic,hostapd-basic-openssl,hostapd-basic-wolfssl,hostapd-mini,hostapd-openssl,hostapd-wolfssl,wpad,wpad-mesh-openssl,wpad-mesh-wolfssl,wpad-basic,wpad-basic-openssl,wpad-basic-wolfssl,wpad-mini,wpad-wolfssl,wpa-supplicant,wpa-supplicant-mesh-openssl,wpa-supplicant-mesh-wolfssl,wpa-supplicant-basic,wpa-supplicant-mini,wpa-supplicant-openssl,wpa-supplicant-p2p,eapol-test,eapol-test-openssl,eapol-test-wolfssl])
      --extra_image_name string                A custom name to add to the image, added as a suffix to existing names.
  -h, --help                                   help for cros_openwrt_image_builder
      --image_builder_url string               URL to download the image builder archive from. Leave unset to use the last downloaded image builder.
      --image_profile string                   The profile to use with the image builder when making images. Leave unset to prompt for selection based off of available profiles.
      --include_custom_package stringArray     Names of packages that should be included in built images that are built using a local sdk and included in the image builder as custom IPKs. Only custom packages in this list are saved from sdk package compilation. (default [cros-send-management-frame,hostapd-common,hostapd-utils,wpad-openssl,wpa-cli])
      --include_official_package stringArray   Names of packages that should be included in built images that are downloaded from official OpenWrt repositories. (default [kmod-veth,tcpdump,procps-ng-pkill,netperf,iperf,sudo])
      --sdk_compile_max_cpus int               The maximum number of CPUs to use for custom package compilation. Values less than 1 indicate that all available CPUs may be used. (default -1)
      --sdk_config stringToString              Config options to set for the sdk when compiling custom packages. (default [CONFIG_WPA_ENABLE_WEP=y,CONFIG_DRIVER_11N_SUPPORT=y,CONFIG_DRIVER_11AC_SUPPORT=y,CONFIG_DRIVER_11AX_SUPPORT=y,CONFIG_WPA_MBO_SUPPORT=y])
      --sdk_make stringArray                   The sdk package makefile paths to use to compile custom IPKs. Making a package with the sdk will build all the IPKs that package depends upon, but only need to be included if they are expected to differ from official versions. (default [cros-send-management-frame,feeds/base/hostapd])
      --sdk_url string                         URL to download the sdk archive from. Leave unset to use the last downloaded sdk.
      --use_existing                           Shortcut to set both --use_existing_sdk and --use_existing_image_builder.
      --use_existing_image_builder             Use image builder in working directory as-is (must exist).
      --use_existing_sdk                       Use sdk in working directory as-is (must exist).
      --working_dir string                     Path to working directory to store downloads, sdk, image builder, and built packages and images. (default "/tmp/cros_openwrt")

Use "cros_openwrt_image_builder [command] --help" for more information about a command.
```

## Project Structure

The `./custom_packages` directory contains source code for custom OpenWrt
packages.

The `./image_builder` directory contains the source code for and builds of the
`cros_openwrt_image_builder` CLI utility.

The `./included_image_files` directory contains files that are added to built
OpenWrt OS images.
