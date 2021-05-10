# New variant of Dedede

[TOC]

Contact `chromeos-scale-taskforce@google.com` for questions.

This tutorial shows how to create the "Acro" variant of Dedede's Waddldee
reference board.

The process for Dedede is very similar to Volteer, except that Dedede
has two reference boards, Waddledee and Waddledoo. The workflow is the
same for either variant; just specify `--board=waddledee` to make a
variant of the Waddledee reference board, or `--board=waddledoo` to
make a variant of the Waddledoo reference board.

Rather than duplicate the explanatory text in each section, we have opted
to only provide the headings, the commands, and any important notes. Refer
to the same-named sections in the Hatch or Volteer tutorials for explanatory
text.

## Per-project configuration repository

A gerrit administrator must create the project configuration repository before
you can begin the process to create a new variant of Dedede. Please file a bug
in [Infra > ChromeOS > Product > Device](https://bugs.chromium.org/p/chromium/issues/list?q=component:Infra%3EChromeOS%3EProduct%3EDevice)
to have the project configuration updated.

This example shows how to create the "Acro" variant of the Waddledee
reference board. Note that there is no project configuration repository
for Acro, but this example proceeds as if it does exist.

## Start the new variant

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --board=waddledee --variant=acro --bug=b:157183582
[... some messages about creating a new coreboot variant and configuration ...]
[... the source files for the new FIT image are created, and then the ...]
[... program exits with a message about building the FIT image ...]
ERROR:root:The following files need to be generated:
ERROR:root:* fitimage-acro.bin
ERROR:root:* fitimage-acro-versions.txt
ERROR:root:The fitimage sources are ready for gen_fit_image.sh to process.
ERROR:root:gen_fit_image.sh cannot run inside the chroot. Please open a new terminal
ERROR:root:window, change to the directory where gen_fit_image.sh is located, and run
ERROR:root:./gen_fit_image.sh acro <path_to_fit_kit> -b
ERROR:root:Then re-start this program with --continue.
ERROR:root:If your chroot is based in ~/chromiumos, then the folder you want is
ERROR:root:~/chromiumos/src/private-overlays/baseboard-dedede-private/sys-boot/coreboot-private-files-baseboard-dedede/asset_generation
```

## Generate the FIT image

Dedede currently uses version 13.50.0.7049 (but the version will likely change
in the future) of Intel's FIT tools, so this example assumes that you have
unzipped the Intel FIT tool files in the directory `~/TXE_JSL`.

```
$ cd ~/chromiumos/src/private-overlays/baseboard-dedede-private/sys-boot/coreboot-private-files-baseboard-dedede/asset_generation
$ ./gen_fit_image.sh acro ~/TXE_JSL -b
```

## Continue creating the variant

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --continue
[... lots of messages about various commits being created ...]
[... the EC code builds ...]
[... the firmware boot image builds (using emerge) ...]
[... the program exits with a message about pushing to coreboot ...]
INFO:root:Running step push_coreboot
ERROR:root:The following commit needs to be pushed to coreboot.org:
ERROR:root:  Branch "create_acro_20200521"
ERROR:root:  in directory "/mnt/host/source/src/third_party/coreboot"
ERROR:root:  with change-id "Ie900d09ff55e695527eafe68a5a75cd4a0b6d340"
ERROR:root:Please push the branch to review.coreboot.org, and then re-start this program with --continue
```

Note that the change-id is the same as Sushi in this example, because the
acro CLs have not been (and will not be) uploaded.

## Push the coreboot CL

## Upload the rest of the CLs

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --continue
INFO:root:Running step push_coreboot
INFO:root:Running step upload_CLs
INFO:root:Running step find_coreboot_upstream
ERROR:root:Program cannot continue until coreboot CL is upstreamed.
ERROR:root:(coreboot:39892, change-id Ie900d09ff55e695527eafe68a5a75cd4a0b6d340)
ERROR:root:Please wait for the CL to be upstreamed, then run this program again with --continue
```

Note that the CL number and change-id is the same as Sushi in this example,
because the acro CLs have not been (and will not be) uploaded.

## Add Cq-Depend information, re-upload, and clean up

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --continue
INFO:root:Running step find_coreboot_upstream
INFO:root:Running step add_cq_depend
INFO:root:Running step re_upload
INFO:root:Running step clean_up
```
