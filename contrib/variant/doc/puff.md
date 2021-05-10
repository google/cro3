# New variant of Puff

[TOC]

Contact `chromeos-scale-taskforce@google.com` for questions.

This tutorial shows how to create the "Wyvern" variant of the Puff reference
board.

The process for Puff is very similar to Volteer.

Rather than duplicate the explanatory text in each section, we have opted
to only provide the headings, the commands, and any important notes. Refer
to the same-named sections in the Hatch or Volteer tutorials for explanatory
text.

## Per-project configuration repository

A gerrit administrator must create the project configuration repository before
you can begin the process to create a new variant of Puff. Please file a bug
in [Infra > ChromeOS > Product > Device](https://bugs.chromium.org/p/chromium/issues/list?q=component:Infra%3EChromeOS%3EProduct%3EDevice)
to have the project configuration updated.

This example shows how to create the "Wyvern" variant of the Puff reference
board. Since Wyvern is a real product, unlike Gnastygnorc (Volteer), Acro
(Dedede), and Grue (Zork), the project configuration repository actually
exists. [CL 3078802](https://crrev.com/i/3078802) created the project
configuration repository.

## Start the new variant

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --board=puff --variant=wyvern --bug=b:158269582
INFO:root:Running step project_config
INFO:root:Started working on 'chromeos-base/chromeos-config-bsp-puff-private' for 'puff'
Calculating dependencies... done!
[... some messages about creating a new coreboot variant and configuration ...]
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

[Full console log - start the new variant](./wyvern1.txt)

## Generate the FIT image

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

[Full console log - generate the FIT image](./wyvern2.txt)

## Continue creating the variant

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

[Full console log - continue the variant](./wyvern3.txt)

## Push the coreboot CL

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

[Full console log - push to coreboot](./wyvern4.txt)

## Upload the rest of the CLs

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

[Full console log - upload the rest of the CLs](./wyvern5.txt)

## Add Cq-Depend information, re-upload, and clean up

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

[Full console log - cq-depend and re-upload](./wyvern6.txt)

## Uploaded CLs for "Wyvern" variant

A screen capture video of the process to create Wyvern is available:
[Wyvern_tutorial_with_subtitles](https://drive.google.com/file/d/1t-JWTSfCyvL-oHmykyi1i5rdSYAyANmm/view?usp=sharing)

The following CLs were created and uploaded by `new_variant.py`:
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
