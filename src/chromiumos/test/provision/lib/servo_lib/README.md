# servo lib

This module allows users to get correct servo-related variables for
flashing, specifically, dut-controls to be run before and after flashing
and the programmer argument.

These arguments mostly* depend on type of the servo in use. Thus, this
module provides utilities to parse the type of the servo.

\* - However, some boards require special arguments, configs for which may
be found
[here](https://source.corp.google.com/chromeos_public/chromite/lib/firmware/ap_firmware_config/).
TODO: get labstations to install those configs via either `cros` tool
(requires cros_sdk) or simply by installing an
[ebuild](https://source.corp.google.com/chromeos_public/src/third_party/chromiumos-overlay/sys-firmware/ap-firmware-config/ap-firmware-config-0.0.1-r238.ebuild;l=1)
and use them.
