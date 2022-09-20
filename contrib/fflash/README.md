# fflash

go/cros-fflash

`fflash` is a tool to update a ChromiumOS device with a test image from `gs://` (Google Cloud Storage).

## Setup & Build

Dependencies:

*   go 1.18 or later. Use `go version` to inspect the version.
*   ninja. Check with `ninja --version`. ninja comes with depot_tools.

### In-repo setup

```
cd ~/chromiumos/src/platform/dev/contrib/fflash
ninja -v
```

### (Alternative) Out of source tree setup

```
git clone https://chromium.googlesource.com/chromiumos/platform/dev-util
cd dev-util/contrib/fflash
ninja -v
```

## Run

1.  Make sure you can `ssh ${dut_host}` without typing a password

2.  ```
    # in the fflash directory
    bin/fflash ${dut_host}
    ```

    Where `${dut_host}` is the ssh target.

## Usage examples

```
bin/fflash ${dut_host}
bin/fflash ${dut_host} -R104
bin/fflash ${dut_host} -R104-14911.0.0
bin/fflash ${dut_host} --board=cherry64 -R104
bin/fflash ${dut_host} --gs=gs://chromeos-image-archive/cherry-release/R104-14911.0.0
bin/fflash --help
```

## What `fflash` does

*   flashes the specified image, or latest image on the device
*   clobbers stateful (optional)
*   disables verified boot
*   clears tpm owner (optional)
*   reboot the device

### it does not

*   ask for sudo password
*   flash minios

`fflash` is faster than `cros flash` if the connection between `cros flash` and the DUT is slow.
`cros flash` proxies the `gs://chromeos-image-archive` images for the DUT (Google Cloud -> workstation -> DUT).
`fflash` makes the DUT download the OS images directly, by granting the DUT a restricted
access token to the Chrome OS release image directory (Google Cloud -> DUT).

## Development

### Run unit tests

```
go test ./...
```

## Bugs & Feedback

Join the [fflash-users](https://groups.google.com/a/google.com/g/fflash-users) Google Group (Googlers only).
