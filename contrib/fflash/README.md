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

*   flashes the latest test image on the device
*   disables verified boot

`fflash` is faster than `cros flash` if the connection between `cros flash` and the DUT is slow.
`cros flash` proxies the `gs://chromeos-image-archive` images for the DUT (Google Cloud -> workstation -> DUT).
`fflash` makes the DUT download the OS images directly, by granting the DUT a restricted
access token to the Chrome OS release image directory (Google Cloud -> DUT).
