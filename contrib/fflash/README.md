# fflash

[go/cros-fflash](https://goto.google.com/cros-fflash)

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
bin/fflash ${dut_host}  # flash latest canary
bin/fflash ${dut_host} --clobber-stateful=yes  # flash latest canary and clobber stateful
bin/fflash ${dut_host} -R104  # flash latest R104
bin/fflash ${dut_host} -R104-14911.0.0  # flash 104-14911.0.0
bin/fflash ${dut_host} --board=cherry64 -R104  # flash latest R104 for board cherry64
bin/fflash ${dut_host} --gs=gs://chromeos-image-archive/cherry-release/R104-14911.0.0  # flash specified gs:// directory
bin/fflash --help
```

## What `fflash` does

*   flashes the specified image, or latest image on the device
*   clobbers stateful (optional, disabled by default)
*   disables verified boot
*   clears tpm owner (optional, disabled by default)
*   reboot the device

### it does not

*   ask for sudo password
*   flash minios

`fflash` is faster than `cros flash` if the connection between `cros flash` and the DUT is slow.
`cros flash` proxies the `gs://chromeos-image-archive` images for the DUT (Google Cloud -> workstation -> DUT).
`fflash` makes the DUT download the OS images directly, by granting the DUT a restricted
access token to the Chrome OS release image directory (Google Cloud -> DUT).

## Development

### Testing

#### Unit tests

```
go test ./...
```

#### Integration tests

```
ninja -v
bin/integration-test ${dut_host}
```

## Bugs & Feedback

*   Join the [fflash-users] Google Group (Googlers only).

*   [File a bug] in our [issue tracker].

[fflash-users]: https://groups.google.com/a/google.com/g/fflash-users
[File a bug]: https://issuetracker.google.com/issues/new?component=1264059
[issue tracker]: https://issuetracker.google.com/issues?q=status:open%20componentid:1264059&s=created_time:desc

## Related tools

*   [cros flash] is the officially supported tool to image ChromiumOS devices.
    It also allow flashing locally-built images.

*   [quick-provision] is useful if your OS image is already on your ChromiumOS device.

[cros flash]: https://chromium.googlesource.com/chromiumos/docs/+/HEAD/cros_flash.md
[quick-provision]: https://source.chromium.org/chromiumos/chromiumos/codesearch/+/main:src/platform/dev/quick-provision/
