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
