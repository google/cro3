# New variant of Volteer

[TOC]

Contact `chromeos-scale-taskforce@google.com` for questions.

This tutorial shows how to create the "Gnastygnorc" variant of the Volteer
reference board.

The process for Volteer is similar to Hatch, but not quite identical.
Hatch uses public and private model.yaml files for configuration, while
Volteer uses the new per-project configuration repository (in
src/project/volteer/${VARIANT}).

A new variant for Hatch involves the following steps:
1. Create coreboot variant
2. Create coreboot configuration
3. Create FIT image
4. Ask user to generate FIT image outside chroot
5. Commit FIT image binaries
6. Create EC image
7. Add configuration to public model.yaml
8. Add configuration to private model.yaml
9. Build project configuration and verify new variant exists
10. Build firmware image for new variant

A new variant for Volteer involves the following steps:
1. Build project configuration and verify new variant exists
2. Create coreboot variant
3. Create coreboot configuration
4. Create FIT image
5. Ask user to generate FIT image outside chroot
6. Commit FIT image binaries
7. Create EC image
8. Build firmware image for new variant

Note that steps 1-6 for Hatch are the same as steps 2-7 for Volteer.

Rather than duplicate the explanatory text in each section, we have opted
to only provide the headings, the commands, and any important notes. Refer
to the same-named sections in the Hatch tutorial for explanatory text.

## Per-project configuration repository

A gerrit administrator must create the project configuration repository before
you can begin the process to create a new variant of Volteer. Please file a bug
to have the project configuration updated using
[go/cros-boxster-bug](go/cros-boxster-bug) or
https://b.corp.google.com/issues/new?component=167276&template=1022133.

This example shows how to create the "Gnastygnorc" variant of the Volteer
reference board. Note that there is no project configuration repository
for gnastygnorc, but this example proceeds as if it does exist.

## Start the new variant

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --board=volteer --variant=gnastygnorc --bug=b:12345
[... some messages about creating a new coreboot variant and configuration ...]
[... the source files for the new FIT image are created, and then the ...]
[... program exits with a message about building the FIT image ...]
ERROR:root:The following files need to be generated:
ERROR:root:* fitimage-gnastygnorc.bin
ERROR:root:* fitimage-gnastygnorc-versions.txt
ERROR:root:The fitimage sources are ready for gen_fit_image.sh to process.
ERROR:root:gen_fit_image.sh cannot run inside the chroot. Please open a new terminal
ERROR:root:window, change to the directory where gen_fit_image.sh is located, and run
ERROR:root:./gen_fit_image.sh gnastygnorc <path_to_fit_kit> -b
ERROR:root:Then re-start this program with --continue.
ERROR:root:If your chroot is based in ~/chromiumos, then the folder you want is
ERROR:root:~/chromiumos/src/private-overlays/baseboard-volteer-private/sys-boot/coreboot-private-files-baseboard-volteer/asset_generation
```

## Generate the FIT image

Volteer uses version 15.0.0.1166 of Intel's FIT tools, so
this example assumes that you have unzipped the Intel FIT tool files in the
directory `~/TXE1166`.

```
$ cd ~/chromiumos/src/private-overlays/baseboard-volteer-private/sys-boot/coreboot-private-files-baseboard-volteer/asset_generation
$ ./gen_fit_image.sh gnastygnorc ~/TXE1166 -b
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
ERROR:root:  Branch "create_gnastygnorc_20200424"
ERROR:root:  in directory "/mnt/host/source/src/third_party/coreboot"
ERROR:root:  with change-id "Ie900d09ff55e695527eafe68a5a75cd4a0b6d340"
ERROR:root:Please push the branch to review.coreboot.org, and then re-start this program with --continue
```

Note that the change-id is the same as Sushi in this example, because the
Gnastygnorc CLs have not been (and will not be) uploaded.

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
because the Gnastygnorc CLs have not been (and will not be) uploaded.

## Add Cq-Depend information, re-upload, and clean up

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --continue
INFO:root:Running step find_coreboot_upstream
INFO:root:Running step add_cq_depend
INFO:root:Running step re_upload
INFO:root:Running step clean_up
```
