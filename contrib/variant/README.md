# Creating Firmware for a New Variant of a Baseboard


ChromeOS device development begins with a Google-developed reference design.
Partners then create unique implementations from that reference, which we refer
to as "variants".

The programs in this directory, plus some additional programs in private
repositories, automate the process of creating the firmware source code for
a new variant by copying and modifying source code from the reference design.
After the base files are created, partners can customize the variant to their
requirements by removing features which they do not want to offer (such as
LTE), change parts (such as LPDDR3 memory instead of DDR4), or add other
differentiating features.

Refer to the
[ChromeOS Partner Site](https://chromeos.google.com/partner/dlm/docs/bringup-tasks/creating_a_device.html)
for more details.

To create a new variant of a baseboard, you must be running inside the chroot
environment. Please ensure that you have successfully synced your tree
(`repo sync`) and that your toolchain is up-to-date (`update_chroot`).
The programs create commits for the new and modified source files, and it is
vital that these commits are based off cros/master.

`new_variant.py` runs the appropriate shell scripts in sequence and builds
the code (via `emerge`) to verify that everything has been copied correctly.
new\_variant.py requires a --board and --variant parameter, and allows an
optional --bug parameter, e.g.
```
$ ./new_variant.py --board=hatch --variant=sushi --bug=b:12345
```
to create the "sushi" variant of the "hatch" baseboard, and associate all of
the commits with bug #12345 in Buganizer. If you omit the `--bug` parameter,
the commit messages will include `BUG=None`.

new_variant.py supports the Hatch baseboad fully. Support for Volteer is
in progress.

At a certain point in the program flow, `new_variant.py` may exit with a
message that you need to run `gen_fit_image.sh` outside of the chroot; open
a new terminal window, change to the appropriate directory, and run the script
indicated. When it has finished, you can return to the chroot environment and
run `./new_variant.py --continue` to resume the program.

These programs are a work in progress. For any questions, problems, or
suggestions, please contact `chromeos-scale-taskforce@google.com`.
