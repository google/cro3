# Creating Firmware for a New Variant of a Reference Board

[TOC]

Contact `chromeos-scale-taskforce@google.com` for questions.

# Background

ChromeOS device development typically begins with a Google-developed reference
design. Partners then create unique implementations from that reference, which
we refer to as "variants".

# Introduction

[`new_variant.py`](https://source.chromium.org/chromiumos/chromiumos/codesearch/+/master:src/platform/dev/contrib/variant/new_variant.py) uses the shell scripts in its same directory, plus some
additional programs in private repositories, to automate the process of
creating the firmware source code for a new variant of an existing reference
board.

The new variant is created as an exact copy of the reference board. After
committing the code for the new variant, partners can customize the variant
to their requirements by removing features which they do not want to offer
(such as LTE), change parts (such as LPDDR3 memory instead of DDR4), or add
other differentiating features.

## Typographic Conventions

For any commands that you are instructed to run, the shell prompt is shown as
`(cr) $` for commands that run inside the chroot, and `$` for commands that
must run outside the chroot.

Output text in some cases may be summarized with `[...` and `...]` containing
a brief explanation of what is happening and what messages will be displayed on
the screen, rather than copying all of the output.

## Prerequisites

* For any board that uses an Intel SoC, you must have the appropriate FIT tools
installed, as well as Wine (`sudo apt-get install wine`) to run the FIT tools.
Obtain the FIT tools directly from [Intel's Resource & Design Center](https://www.intel.com/content/www/us/en/my-intel/design-center-sign-in.html)

* Please ensure that you have successfully synced your tree, and that your
toolchain is up-to-date:
	```
	$ cd ~/chromiumos
	$ cros_sdk -- bash -c "repo sync && ./update_chroot"
	```

* `new_variant.py` must run inside the ChromeOS `chroot` environment.

* A bug number to track the creation of the firmware for the new variant,
e.g. b/133181366 to create the Kindred variant of Hatch.

# Tutorials

The tutorials cover the process of creating the firmware for a new variant
of a reference board. There are examples for [Hatch](doc/hatch.md),
[Volteer](doc/volteer.md), [Dedede](doc/dedede.md), [Zork](doc/zork.md), and
[Puff](doc/puff.md).

# Additional Information

## Program state

`new_variant.py` keeps track of its state inside the chroot in the user's
home directory. The state is stored in a file named `.new_variant.yaml`.
The `--continue` option uses the state to continue the creation of the
new variant.

## Abort
If you want to abort the creation of the new variant, use the `--abort`
flag, e.g. `./new_variant.py --abort`. All of the branches and commits that
were created on your local disk for the new variant will be abandoned and
deleted, and the stored state (`.new_variant.yaml`) will be cleaned up.

Any CLs that have been uploaded will continue to exist on the gerrit servers;
make sure to abandon the CLs using the gerrit interface.

# References

* [Working with coreboot Upstream and Chromium](https://chromium.googlesource.com/chromiumos/docs/+/refs/heads/master/firmware/coreboot_upstream.md)
* [How To: Building coreboot-upstream within Chromium OS](https://docs.google.com/document/d/1H7u99Pk0EGqcsROciFyoXIdpsL-AwcpfJG7VI2UDNFw/)
* [ChromeOS Unibuild New Variant Design Doc](https://docs.google.com/document/d/1nAJblS29W4SMsGPPijfZED1QRYFMHeW2w_9ooPvEO_U)
