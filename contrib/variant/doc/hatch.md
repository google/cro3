# New variant of Hatch

[TOC]

Contact `chromeos-scale-taskforce@google.com` for questions.

This tutorial shows how to create the "Sushi" variant of the Hatch reference
board.

## Start the new variant

Enter the chroot and start the variant by running `./new_variant.py` and
providing the name of the reference board (Hatch), the name of the new
variant (Sushi), and the bug number (or "None"). `new_variant.py` will
create CLs for a new coreboot variant, a new coreboot configuration, and a
new FIT image. The program will then ask you to generate the FIT image
outside the chroot environment.

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --board=hatch --variant=sushi --bug=None
[... some messages about creating a new coreboot variant and configuration ...]
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

## Generate the FIT image

Open a new terminal and do not enter the `chroot` environment. Hatch uses
version 14.0.0.1065 of Intel's FIT tools, so this example
assumes that you have unzipped the Intel FIT tool files in the directory
`~/TXE1065`.

```
$ cd ~/chromiumos/src/private-overlays/baseboard-hatch-private/sys-boot/coreboot-private-files-hatch/asset_generation
$ ./gen_fit_image.sh sushi ~/TXE1065 -b
```

When FIT image generation is done, you can close this terminal

## Continue creating the variant

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

## Push the coreboot CL

Push the commit to coreboot as instructed. There are multiple ways to push a
CL to `review.coreboot.org`; if you have a method that works for you, do that.
If not, see the References section for documents that explain some possible
workflows for pushing to coreboot.
Because your setup may vary, the specific commands are beyond the scope of
this document.

## Upload the rest of the CLs

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

## Add Cq-Depend information, re-upload, and clean up

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

## Uploaded CLs for "Sushi" variant

The following CLs were created and uploaded by `new_variant.py`:
* [39892](https://review.coreboot.org/c/coreboot/+/39892) hatch: Create sushi
variant
  * The Upstream CL is [2126753](https://crrev.com/c/2126753), which was not
  created by `new_variant.py`.
* [2125270](https://crrev.com/c/2125270) hatch: Add sushi coreboot configuration
* [2819185](https://crrev.com/i/2819185) hatch: Add fitimage for sushi
* [2125163](https://crrev.com/c/2125163) sushi: Initial EC image
* [2820196](https://crrev.com/i/2820196) model.yaml: Add sushi variant
* [2125164](https://crrev.com/c/2125164) model.yaml: Add sushi variant
