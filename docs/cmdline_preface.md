> [!NOTE]
> This guide is automatically generated from doc comments in `src/cmd/*.rs`.
> To update the contents, please edit the source files and rebuild cro3.

## Variables used in this guide

- `$CROS`
  - `/path/to/chromiumos`
- `$DUT`
  - `127.0.0.1` for IPv4 address
  - `[2001:db8::1234]` for IPv6 address
  - `dut_id` which contains `model_name` and `serial_number`
    - `cros dut list` displays the `dut_id` for registered DUTs
- `$BOARD`
  - `eve` for example
  - Same as `BOARD` variable explained in [the official documentation](https://chromium.googlesource.com/chromiumos/docs/+/HEAD/developer_guide.md#Select-a-board)
