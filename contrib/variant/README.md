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
of a reference board. There are examples for Hatch, Volteer, Dedede, and
Zork.

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
