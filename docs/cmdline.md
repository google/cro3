> [!NOTE]
> This guide is automatically generated from doc comments in `src/cmd/*.rs`.
> To update the contents, please edit the source files and rebuild cro3.

## Variables used in this guide

- `$CROS`
  - `/path/to/chromiumos`
  - Relative paths are also accepted
- `$DUT`
  - All things listed under `$IP`, plus...
  - `dut_id` which contains `model_name` and `serial_number`, connected with `_`, e.g. `boten_PF2LBG2H`.
    - `cros dut list` displays the `dut_id` for registered DUTs
- `$BOARD`
  - `eve` for example
  - Same as `BOARD` variable explained in [the official documentation](https://chromium.googlesource.com/chromiumos/docs/+/HEAD/developer_guide.md#Select-a-board)
- `$IP`
  - Something like `192.0.2.1` for IPv4 address
  - Something like `[2001:db8::1234]` for IPv6 address
  - Usually this is used to refer a DUT for the first time. If the parameter accepts `dut_id` as well, please use `$DUT` instead.
- `$PACKAGE_NAME`
  - A portage package name to be built / deployed / worked on
  - e.g. `chromeos-base/system_api` `crosvm`
## ARC (Android Runtime on Chrome) related utilities
This feature is mainly for the internal developers.
## Build packages and images
```
cro3 build --cros $CROS --board brya --packages sys-kernel/arcvm-kernel-ack-5_10
cro3 build --full --cros $CROS --board brya
```
## Config cro3 behavior
```
cro3 config set default_cros_checkout /work/chromiumos_stable/
cro3 config show
```
## Deploy packages
```
cro3 deploy --cros $CROS --dut $DUT --package $PACKAGE_NAME --autologin
```
## DUT (Device Under Test) management
```
# SSH into a DUT using testing_rsa
cro3 dut shell --dut ${DUT}

# Execute a shell command on a DUT
cro3 dut shell --dut ${DUT} -- uname -a

# Add a DUT to the list
cro3 dut list --add ${IP}

# Show the list of DUTs registered
cro3 dut list

# Check connection and remove DUTs that have reused IP addresses
cro3 dut list --update

# Show DUT info
cro3 dut info --dut ${DUT}

# Show specific DUT info (e.g. ipv6_addr)
cro3 dut info --dut ${DUT} ipv6_addr

# Scan DUTs on the same network where `--remote` is connected.
cro3 dut discover --remote ${IP} | tee /tmp/dut_discovered.json
# Monitor DUTs and keep them accessible via local port forwarding
cro3 dut monitor ${DUT}
```
## Flash images (cros flash wrapper)
```
# Flash an image into a remote DUT
cro3 flash --cros ${CROS} --dut ${DUT}
# Flash an image into a USB stick
cro3 flash --cros ${CROS} --usb --board ${BOARD}
```
## Controlling a Servo (Hardware debugging tool)
Note: the official document is [here](https://chromium.googlesource.com/chromiumos/third_party/hdctools/+/HEAD/docs/servo.md)
```
# Show list of Servo / Cr50 devices
cro3 servo list

# Do the same thing in JSON format
cro3 servo list --json

# Reset Servo USB ports (useful when cro3 servo list does not work)
sudo `which cro3` servo reset
```
## Get / update a ChromiumOS source checkout (similar to `git clone` or `git pull`)
```
cro3 sync --cros /work/chromiumos_stable/ --version 14899.0.0
cro3 sync --cros /work/chromiumos_stable/ --version R110-15263.0.0
# following command needs a mirror repo which has cloned with --mirror option
cro3 sync --cros /work/chromiumos_versions/R110-15248.0.0/ --version R110-15248.0.0 --reference /work/chromiumos_mirror/
cro3 sync --cros /work/chromiumos_versions/R110-15248.0.0/ --version R110-15248.0.0 # you can omit --reference if the config is set
```
