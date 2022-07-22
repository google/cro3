# fflash

## Setup

1.  Install go 1.18 or later. Use `go version` to inspect the version.
2.  Clone & build

    ```
    git clone https://chromium.googlesource.com/chromiumos/platform/dev-util
    cd dev-util/contrib/fflash
    bash build.bash
    ```

## Run

```
# in the fflash directory
bin/fflash ${dut_host}
```

Where `${dut_host}` is the ssh target.

`fflash` currently:

*   flashes the specified image, or latest image on the device
*   clobbers stateful
*   disables verified boot
*   clears tpm owner
*   reboot the device

`fflash` is faster than `cros flash` if the connection between `cros flash` and the DUT is slow.
`cros flash` proxies the `gs://chromeos-image-archive` images for the DUT (Google Cloud -> workstation -> DUT).
`fflash` makes the DUT download the OS images directly, by granting the DUT a restricted
access token to the Chrome OS release image directory (Google Cloud -> DUT).

## Usage examples

```
bin/fflash ${dut_host}
bin/fflash ${dut_host} -R104
bin/fflash ${dut_host} -R104-14911.0.0
bin/fflash ${dut_host} --gs=gs://chromeos-image-archive/cherry-release/R104-14911.0.0
bin/fflash --help
```
