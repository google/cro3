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
of a reference board. There are examples for Hatch, Volteer, Dedede, Zork,
and Puff.

## New variant of Hatch

This example shows how to ceate the "Sushi" variant of the Hatch reference
board.

### Start the new variant

Enter the chroot and start the variant by running `./new_variant.py` and
providing the name of the reference board (Hatch), the name of the new
variant (Sushi), and the bug number (or "None"). `new_variant.py` will
create CLs for a new coreboot variant, a new coreboot configuration, and a
new FIT image. The program will then ask you to generate the FIT image
outside the chroot environment.

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --board=hatch --variant=sushi --bug=None
[... some messages about creating a new coreboot variant and configuation ...]
[... the source files for the new FIT image are created, and then the ...]
[... program exits with a message about building the FIT image ...]
ERROR:root:The following files need to be generated:
ERROR:root:* fitimage-sushi.bin
ERROR:root:* fitimage-sushi-versions.txt
ERROR:root:The fitimage sources are ready for gen_fit_image.sh to process.
ERROR:root:gen_fit_image.sh cannot run inside the chroot. Please open a new terminal
ERROR:root:window, change to the directory where gen_fit_image.sh is located, and run
ERROR:root:./gen_fit_image.sh sushi <path_to_fit_kit> -b
ERROR:root:Then re-start this program with --continue.
ERROR:root:If your chroot is based in ~/chromiumos, then the folder you want is
ERROR:root:~/chromiumos/src/private-overlays/baseboard-hatch-private/sys-boot/coreboot-private-files-hatch/asset_generation
```

### Generate the FIT image

Open a new terminal and do not enter the `chroot` environment. Hatch uses
version 14.0.0.1065 of Intel's FIT tools, so this example
assumes that you have unzipped the Intel FIT tool files in the directory
`~/TXE1065`.

```
$ cd ~/chromiumos/src/private-overlays/baseboard-hatch-private/sys-boot/coreboot-private-files-hatch/asset_generation
$ ./gen_fit_image.sh sushi ~/TXE1065 -b
```

When FIT image generation is done, you can close this terminal

### Continue creating the variant

Switch back to the terminal still in the `chroot` environment and run
`new_variant.py --continue`.
`new_variant.py` will add the generated FIT image to a CL, then create CLs
for a new EC image and to modify the public and private `model.yaml` files.
It will then ask you to push the coreboot CL to review.coreboot.org.

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --continue
[... lots of messages about various commits being created ...]
[... the EC code builds ...]
[... the firmware boot image builds (using emerge) ...]
[... the program exits with a message about pushing to coreboot ...]
INFO:root:Running step push_coreboot
ERROR:root:The following commit needs to be pushed to coreboot.org:
ERROR:root:  Branch "create_sushi_20200320"
ERROR:root:  in directory "/mnt/host/source/src/third_party/coreboot"
ERROR:root:  with change-id "Ie900d09ff55e695527eafe68a5a75cd4a0b6d340"
ERROR:root:Please push the branch to review.coreboot.org, and then re-start this program with --continue
```

### Push the coreboot CL

Push the commit to coreboot as instructed. There are multiple ways to push a
CL to `review.coreboot.org`; if you have a method that works for you, do that.
If not, see the References section for documents that explain some possible
workflows for pushing to coreboot.
Because your setup may vary, the specific commands are beyond the scope of
this document.

### Upload the rest of the CLs

After the coreboot CL has been pushed, run `new_variant.py --continue` again.
The program will determine that the coreboot CL has been pushed, and then move
on to uploading the other CLs by calling `repo upload`.

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

As part of developing for coreboot in ChromeOS, we have to push our changes
to review.coreboot.org and then wait for those CLs to be reviewed, approved,
merged, and upstreamed into the chromiumos tree. `new_variant.py` will try
to locate the upstreamed CL in the chromiumos tree. If it is not found, the
program will ask you to wait for the CL to be upstreamed before continuing.

### Add Cq-Depend information, re-upload, and clean up

Once the coreboot CL has been upstreamed into the chromiumos tree, you are
ready to re-upload the CLs with new commit messages that add Cq-Depend
information. Again, `new_variant.py` will call `repo upload` to upload new
patchsets on any CL that has Cq-Depend added. Once the uploads are done,
the program will clean up some internal housekeeping information and you are
ready to get the CLs reviewed, approved, and merged.

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --continue
INFO:root:Running step find_coreboot_upstream
INFO:root:Running step add_cq_depend
INFO:root:Running step re_upload
INFO:root:Running step clean_up
```

The `clean_up` step will remove all of the state information that
`new_variant.py` has been tracking during this process.

### Uploaded CLs for "Sushi" variant

The following CLs were created and uplodaded by `new_variant.py`:
* [39892](https://review.coreboot.org/c/coreboot/+/39892) hatch: Create sushi
variant
  * The Upstream CL is [2126753](https://crrev.com/c/2126753), which was not
  created by `new_variant.py`.
* [2125270](https://crrev.com/c/2125270) hatch: Add sushi coreboot configuration
* [2819185](https://crrev.com/i/2819185) hatch: Add fitimage for sushi
* [2125163](https://crrev.com/c/2125163) sushi: Initial EC image
* [2820196](https://crrev.com/i/2820196) model.yaml: Add sushi variant
* [2125164](https://crrev.com/c/2125164) model.yaml: Add sushi variant

## New variant of Volteer

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

### Per-project configuration repository

A gerrit administrator must create the project configuration repository before
you can begin the process to create a new variant of Volteer. Please file a bug
in [Infra > ChromeOS > Product > Device](https://bugs.chromium.org/p/chromium/issues/list?q=component:Infra%3EChromeOS%3EProduct%3EDevice)
to have the project configuration updated.

This example shows how to create the "Gnastygnorc" variant of the Volteer
reference board. Note that there is no project configuration repository
for gnastygnorc, but this example proceeds as if it does exist.

### Start the new variant

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --board=volteer --variant=gnastygnorc --bug=b:12345
[... some messages about creating a new coreboot variant and configuation ...]
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

### Generate the FIT image

Volteer uses version 15.0.0.1166 of Intel's FIT tools, so
this example assumes that you have unzipped the Intel FIT tool files in the
directory `~/TXE1166`.

```
$ cd ~/chromiumos/src/private-overlays/baseboard-volteer-private/sys-boot/coreboot-private-files-baseboard-volteer/asset_generation
$ ./gen_fit_image.sh gnastygnorc ~/TXE1166 -b
```

### Continue creating the variant

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

### Push the coreboot CL

### Upload the rest of the CLs

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

### Add Cq-Depend information, re-upload, and clean up

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --continue
INFO:root:Running step find_coreboot_upstream
INFO:root:Running step add_cq_depend
INFO:root:Running step re_upload
INFO:root:Running step clean_up
```

## New variant of Dedede

The process for Dedede is very similar to Volteer, except that Dedede
has two reference boards, Waddledee and Waddledoo. The workflow is the
same for either variant; just specify `--board=waddledee` to make a
variant of the Waddledee reference board, or `--board=waddledoo` to
make a variant of the Waddledoo reference board.

Rather than duplicate the explanatory text in each section, we have opted
to only provide the headings, the commands, and any important notes. Refer
to the same-named sections in the Hatch or Volteer tutorials for explanatory
text.

### Per-project configuration repository

A gerrit administrator must create the project configuration repository before
you can begin the process to create a new variant of Dedede. Please file a bug
in [Infra > ChromeOS > Product > Device](https://bugs.chromium.org/p/chromium/issues/list?q=component:Infra%3EChromeOS%3EProduct%3EDevice)
to have the project configuration updated.

This example shows how to create the "Acro" variant of the Waddledee
reference board. Note that there is no project configuration repository
for Acro, but this example proceeds as if it does exist.

### Start the new variant

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --board=waddledee --variant=acro --bug=b:157183582
[... some messages about creating a new coreboot variant and configuation ...]
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

### Generate the FIT image

Dedede currently uses version 13.50.0.7049 (but the version will likely change
in the future) of Intel's FIT tools, so this example assumes that you have
unzipped the Intel FIT tool files in the directory `~/TXE_JSL`.

```
$ cd ~/chromiumos/src/private-overlays/baseboard-dedede-private/sys-boot/coreboot-private-files-baseboard-dedede/asset_generation
$ ./gen_fit_image.sh acro ~/TXE_JSL -b
```

### Continue creating the variant

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

### Push the coreboot CL

### Upload the rest of the CLs

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

### Add Cq-Depend information, re-upload, and clean up

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --continue
INFO:root:Running step find_coreboot_upstream
INFO:root:Running step add_cq_depend
INFO:root:Running step re_upload
INFO:root:Running step clean_up
```

## New variant of Zork

The Zork baseboard has two reference boards: Trembyle and Dalboz. This example
will show creation of a variant of Trembyle, but the process for Dalboz is
identical except for the name.

Zork uses the new per-project configuration repository (in
src/project/zork/${VARIANT}).

A new variant for Zork involves the following steps:
1. Build project configuration and verify new variant exists
2. Create coreboot variant
3. Create coreboot configuration
4. Create the CRAS (ChromeOS Audio Server) configuration
5. Create EC image
6. Build firmware image for new variant

### Per-project configuration repository

A gerrit administrator must create the project configuration repository before
you can begin the process to create a new variant of Zork. Please file a bug
in [Infra > ChromeOS > Product > Device](https://bugs.chromium.org/p/chromium/issues/list?q=component:Infra%3EChromeOS%3EProduct%3EDevice)
to have the project configuration updated.

This example shows how to create the "Grue" variant of the Trembyle
reference board. Note that there is no project configuration repository
for grue, but this example proceeds as if it does exist.

### Create the new variant and upload the CLs

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --board=trembyle --variant=grue --bug=b:12345
[... the project config builds (using emerge) ... ]
[... messages about creating a new coreboot variant ...]
[... messages about creating a new coreboot configuration ...]
[... messages about creating a new CRAS configuration ...]
[... the EC code builds ...]
[... the firmware boot image builds (using emerge) ...]
INFO:root:Running step upload_CLs
INFO:root:Running step calc_cq_depend
INFO:root:Running step add_cq_depend
INFO:root:Running step re_upload
INFO:root:Running step clean_up
```

Because Zork is using a firmware branch in coreboot (trembyle-bringup), there
is no need to exit the program and ask the user to push the coreboot variant
to review.coreboot.org. The coreboot CL can be directly uploaded to the
chromium gerrit instance. This will of course change when the trembyle-bringup
branch is merged into coreboot upstream. (TODO b/157570490)

### Using Dalboz as the reference board

Note that using Dalboz as the reference board only requires using
`--board=dalboz` instead of `--board=trembyle`:

```
./new_variant.py --board=dalboz --variant=grue --bug=b:12345
```

## New variant of Puff

The process for Puff is very similar to Volteer.

Rather than duplicate the explanatory text in each section, we have opted
to only provide the headings, the commands, and any important notes. Refer
to the same-named sections in the Hatch or Volteer tutorials for explanatory
text.

### Per-project configuration repository

A gerrit administrator must create the project configuration repository before
you can begin the process to create a new variant of Puff. Please file a bug
in [Infra > ChromeOS > Product > Device](https://bugs.chromium.org/p/chromium/issues/list?q=component:Infra%3EChromeOS%3EProduct%3EDevice)
to have the project configuration updated.

This example shows how to create the "Wyvern" variant of the Puff reference
board.

### Start the new variant

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --board=puff --variant=wyvern --bug=b:158269582
INFO:root:Running step project_config
INFO:root:Started working on 'chromeos-base/chromeos-config-bsp-puff-private' for 'puff'
Calculating dependencies... done!
[... some messages about creating a new coreboot variant and configuation ...]
[... the source files for the new FIT image are created, and then the ...]
[... program exits with a message about building the FIT image ...]
INFO:root:Running step gen_fit_image_outside_chroot
ERROR:root:The following files need to be generated:
ERROR:root:* fitimage-wyvern.bin
ERROR:root:* fitimage-wyvern-versions.txt
ERROR:root:The fitimage sources are ready for gen_fit_image.sh to process.
ERROR:root:gen_fit_image.sh cannot run inside the chroot. Please open a new terminal
ERROR:root:window, change to the directory where gen_fit_image.sh is located, and run
ERROR:root:./gen_fit_image.sh wyvern <path_to_fit_kit> -b
ERROR:root:Then re-start this program with --continue.
ERROR:root:If your chroot is based in ~/chromiumos, then the folder you want is
ERROR:root:~/chromiumos/src/private-overlays/baseboard-puff-private/sys-boot/coreboot-private-files-puff/asset_generation
```

### Generate the FIT image

Puff uses version 14.0.40.1206 of Intel's FIT tools, so this example assumes
that you have unzipped the Intel FIT tool files in the directory `~/TXE/puff`.

```
$ cd ~/chromiumos/src/private-overlays/baseboard-puff-private/sys-boot/coreboot-private-files-puff/asset_generation
$ ./gen_fit_image.sh wyvern ~/TXE/puff -b
===============================================================================
Intel (R) Flash Image Tool. Version: 14.0.40.1206
Copyright (c) 2013 - 2020, Intel Corporation. All rights reserved.
6/18/2020 - 9:09:50 pm
===============================================================================
[... messages about processing attributes and generating output files ...]
```

### Continue creating the variant

Note that there is no CL for the EC code; all Puff variants share the same EC
code base.

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --continue
[... lots of messages about various commits being created ...]
[... the firmware boot image builds (using emerge) ...]
[... the program exits with a message about pushing to coreboot ...]
INFO:root:Running step push_coreboot
ERROR:root:The following commit needs to be pushed to coreboot.org:
ERROR:root:  Branch "coreboot_wyvern_20200618"
ERROR:root:  in directory "/mnt/host/source/src/third_party/coreboot"
ERROR:root:  with change-id "Id7a090058d2926707495387f7e90b3b8ed83dac7"
ERROR:root:Please push the branch to review.coreboot.org, and then re-start this program with --continue
```

### Push the coreboot CL

Per [Working with coreboot Upstream and Chromium], push the coreboot CL to
`review.coreboot.org`.

```
$ cd ~/devel/coreboot
$ git remote update
Fetching upstream
Fetching cros-coreboot
remote: Enumerating objects: 228168, done.
remote: Counting objects: 100% (228104/228104), done.
remote: Compressing objects: 100% (72312/72312), done.
Receiving objects: 100% (222023/222023), 62.53 MiB | 32.16 MiB/s, done.
remote: Total 222023 (delta 170729), reused 194739 (delta 144771), pack-reused 0
Resolving deltas: 100% (170729/170729), completed with 4804 local objects.
From /home/pfagerburg/chromiumos/src/third_party/coreboot
 * [new branch]              coreboot_wyvern_20200618 -> cros-coreboot/coreboot_wyvern_20200618
$ git checkout upstream_master
M	3rdparty/libgfxinit
M	3rdparty/vboot
Already on 'upstream_master'
Your branch is up to date with 'upstream/master'.
$ git pull
Already up to date.
$ git cherry-pick cros-coreboot/coreboot_wyvern_20200618
[upstream_master 992130a17a3] hatch: Create wyvern variant
 Date: Thu Jun 18 21:06:18 2020 -0600
 7 files changed, 35 insertions(+)
 create mode 100644 src/mainboard/google/hatch/variants/wyvern/Makefile.inc
 create mode 100644 src/mainboard/google/hatch/variants/wyvern/include/variant/acpi/dptf.asl
 create mode 100644 src/mainboard/google/hatch/variants/wyvern/include/variant/ec.h
 create mode 100644 src/mainboard/google/hatch/variants/wyvern/include/variant/gpio.h
 create mode 100644 src/mainboard/google/hatch/variants/wyvern/overridetree.cb
$ git push upstream HEAD:refs/for/master
Enumerating objects: 26, done.
Counting objects: 100% (26/26), done.
Delta compression using up to 72 threads
Compressing objects: 100% (16/16), done.
Writing objects: 100% (18/18), 1.81 KiB | 1.81 MiB/s, done.
Total 18 (delta 8), reused 3 (delta 0), pack-reused 0
remote: Resolving deltas: 100% (8/8)
remote: Processing changes: refs: 1, new: 1, done
remote:
remote: SUCCESS
remote:
remote:   https://review.coreboot.org/c/coreboot/+/42551 hatch: Create wyvern variant [NEW]
remote:
To ssh://review.coreboot.org:29418/coreboot.git
 * [new branch]              HEAD -> refs/for/master
```

### Upload the rest of the CLs

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --continue
INFO:root:Running step push_coreboot
INFO:requests.packages.urllib3.connectionpool:Starting new HTTPS connection (1): review.coreboot.org
Found (coreboot, 42551), saving to yaml
INFO:root:Running step upload_CLs
INFO:requests.packages.urllib3.connectionpool:Starting new HTTPS connection (1): review.coreboot.org
[COMMIT 1/1 646dc060f1fe] puff: Add wyvern coreboot configuration
[PASSED] repohooks passed in 0:00:00.085175
Upload project src/third_party/chromiumos-overlay/ to remote branch refs/heads/master:
  branch create_wyvern_20200618 ( 1 commit, Thu Jun 18 21:06:18 2020 -0600):
         646dc060 puff: Add wyvern coreboot configuration
to https://chromium-review.googlesource.com (y/N)? <--yes>
remote: Processing changes: refs: 1, new: 1, done
remote:
remote: SUCCESS
remote:
remote:   https://chromium-review.googlesource.com/c/chromiumos/overlays/chromiumos-overlay/+/2252826 puff: Add wyvern coreboot configuration [WIP] [NEW]
remote:
To https://chromium-review.googlesource.com/chromiumos/overlays/chromiumos-overlay
 * [new branch]              create_wyvern_20200618 -> refs/for/master%wip

----------------------------------------------------------------------
[OK    ] src/third_party/chromiumos-overlay/ create_wyvern_20200618
Found (chromium, 2252826), saving to yaml
INFO:requests.packages.urllib3.connectionpool:Starting new HTTPS connection (1): review.coreboot.org
[COMMIT 1/1 f84f27faf371] puff: Add fitimage for wyvern
[PASSED] repohooks passed in 0:00:00.067894
Upload project src/private-overlays/baseboard-puff-private/ to remote branch refs/heads/master:
  branch create_wyvern_20200618 ( 1 commit, Thu Jun 18 21:11:09 2020 -0600):
         f84f27fa puff: Add fitimage for wyvern
to https://chrome-internal-review.googlesource.com (y/N)? <--yes>
remote: Processing changes: refs: 1, new: 1, done
remote:
remote: SUCCESS
remote:
remote:   https://chrome-internal-review.googlesource.com/c/chromeos/overlays/baseboard-puff-private/+/3122979 puff: Add fitimage for wyvern [WIP] [NEW]
remote:
To https://chrome-internal-review.googlesource.com/chromeos/overlays/baseboard-puff-private
 * [new branch]      create_wyvern_20200618 -> refs/for/master%wip

----------------------------------------------------------------------
[OK    ] src/private-overlays/baseboard-puff-private/ create_wyvern_20200618
Found (chrome-internal, 3122979), saving to yaml
INFO:requests.packages.urllib3.connectionpool:Starting new HTTPS connection (1): review.coreboot.org
[COMMIT 1/1 46d455a21ce4] wyvern: enable default firmware build
[PASSED] repohooks passed in 0:00:07.158037
Upload project src/project/puff/wyvern/ to remote branch refs/heads/master:
  branch create_wyvern_20200618 ( 1 commit, Thu Jun 18 21:06:17 2020 -0600):
         46d455a2 wyvern: enable default firmware build
to https://chrome-internal-review.googlesource.com (y/N)? <--yes>
remote: Processing changes: refs: 1, new: 1, done
remote:
remote: SUCCESS
remote:
remote:   https://chrome-internal-review.googlesource.com/c/chromeos/project/puff/wyvern/+/3122980 wyvern: enable default firmware build [WIP] [NEW]
remote:
To https://chrome-internal-review.googlesource.com/chromeos/project/puff/wyvern
 * [new branch]      create_wyvern_20200618 -> refs/for/master%wip

----------------------------------------------------------------------
[OK    ] src/project/puff/wyvern/ create_wyvern_20200618
INFO:root:Running step find_coreboot_upstream
ERROR:root:Program cannot continue until coreboot CL is upstreamed.
ERROR:root:(coreboot:42551, change-id Id7a090058d2926707495387f7e90b3b8ed83dac7)
ERROR:root:Please wait for the CL to be upstreamed, then run this program again with --continue
```

### Add Cq-Depend information, re-upload, and clean up

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --continue
INFO:root:Running step find_coreboot_upstream
INFO:root:Running step calc_cq_depend
INFO:root:Running step add_cq_depend
Rewrite 646dc060f1fe2c322c51def45ab9249d89148389 (1/1) (0 seconds passed, remaining 0 predicted)
Ref 'refs/heads/create_wyvern_20200618' was rewritten
Rewrite 46d455a21ce4791732b1ef826f5f5b9fc6660173 (1/1) (0 seconds passed, remaining 0 predicted)
Ref 'refs/heads/create_wyvern_20200618' was rewritten
INFO:root:Running step re_upload
[COMMIT 1/1 6bb367ff5ebf] puff: Add wyvern coreboot configuration
[PASSED] repohooks passed in 0:00:00.093924
Upload project src/third_party/chromiumos-overlay/ to remote branch refs/heads/master:
  branch create_wyvern_20200618 ( 1 commit, Thu Jun 18 21:06:18 2020 -0600):
         6bb367ff puff: Add wyvern coreboot configuration
to https://chromium-review.googlesource.com (y/N)? <--yes>
remote: Processing changes: refs: 1, updated: 1, done
remote: warning: 6bb367f: no files changed, message updated
remote:
remote: SUCCESS
remote:
remote:   https://chromium-review.googlesource.com/c/chromiumos/overlays/chromiumos-overlay/+/2252826 puff: Add wyvern coreboot configuration [WIP]
remote:
To https://chromium-review.googlesource.com/chromiumos/overlays/chromiumos-overlay
 * [new branch]              create_wyvern_20200618 -> refs/for/master%wip

----------------------------------------------------------------------
[OK    ] src/third_party/chromiumos-overlay/ create_wyvern_20200618
[COMMIT 1/1 f20f4a265340] wyvern: enable default firmware build
[PASSED] repohooks passed in 0:00:06.741477
Upload project src/project/puff/wyvern/ to remote branch refs/heads/master:
  branch create_wyvern_20200618 ( 1 commit, Wed Jun 24 10:05:59 2020 -0600):
         f20f4a26 wyvern: enable default firmware build
to https://chrome-internal-review.googlesource.com (y/N)? <--yes>
remote: Processing changes: refs: 1, updated: 1, done
remote: warning: f20f4a2: no files changed, message updated
remote:
remote: SUCCESS
remote:
remote:   https://chrome-internal-review.googlesource.com/c/chromeos/project/puff/wyvern/+/3122980 wyvern: enable default firmware build [WIP]
remote:
To https://chrome-internal-review.googlesource.com/chromeos/project/puff/wyvern
 * [new branch]      create_wyvern_20200618 -> refs/for/master%wip

----------------------------------------------------------------------
[OK    ] src/project/puff/wyvern/ create_wyvern_20200618
INFO:root:Running step clean_up
(cr) $
```

### Uploaded CLs for "Wyvern" variant

The following CLs were created and uplodaded by `new_variant.py`:
* [42551](https://review.coreboot.org/c/coreboot/+/42551) hatch: Create wyvern
variant
  * The Upstream CL is [2260221](https://crrev.com/c/2260221), which was not
  created by `new_variant.py`.
* [2252826](https://crrev.com/c/2252826) puff: Add wyvern coreboot configuration
* [3122979](https://crrev.com/i/3122979) puff: Add fitimage for wyvern
* [3122980](https://crrev.com/i/3122980) wyvern: enable default firmware
build

Note that while [3122980](https://crrev.com/i/3122980) was still in review,
it was obsoleted by [3133943](https://crrev.com/i/3133943) Wyvern: Add configs
for SKUs and f/w. The original CL has been abandoned, but is listed here for
completeness.

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

* [Working with coreboot Upstream and Chromium](https://docs.google.com/document/d/14IBkP2Mk-2FtI26VINQRCuMA-vyhuRdSpHHaTfujS9Q/)
* [How To: Building coreboot-upstream within Chromium OS](https://docs.google.com/document/d/1H7u99Pk0EGqcsROciFyoXIdpsL-AwcpfJG7VI2UDNFw/)
* [ChromeOS Unibuild New Variant Design Doc](https://docs.google.com/document/d/1nAJblS29W4SMsGPPijfZED1QRYFMHeW2w_9ooPvEO_U)
