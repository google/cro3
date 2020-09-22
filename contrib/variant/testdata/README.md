Test data for new\_variant.py
============================

Finding the coreboot CL
-----------------------
Test the following cases:
* the CL hasn't been pushed to review.coreboot.org yet
* the CL has been pushed, but has not been upstreamed into the chromiumos tree yet
* the CL has been upstreamed into chromiumos

The test yaml files include the CLs for the creation of the Kindred variant.
The coreboot CL for Kindred is coreboot:32936, and was upstreamed as
chromium:1641906. These CLs have long since merged, and so nothing will be
uploaded to any gerrit instances or merged into ToT.

`need_to_push.yaml` has the change\_id for the coreboot CL modified so that
the CL cannot be found, which makes it look like the CL has not been pushed.
The program will ask the user to push it to coreboot.

`need_to_upstream.yaml` also has the change\_id for the coreboot CL modified,
but the gerrit instance (coreboot) and CL number (32936) are already there,
so the CL has already been found. However, searching chromium for that
change\_id as an original-change-id will fail, indicating that the CL has
not been upstreamed from coreboot yet.

`upstreamed.yaml` has the correct change\_id for the coreboot CL. The program
will find the CL in coreboot, then find the upstreamed CL in chromium, and
proceed to the cq\_depend step (which is not yet implemented).

```
(cr) $ cp testdata/need_to_push.yaml ~/.new_variant.yaml
(cr) $ ./new_variant.py --continue
INFO:root:Running step push_coreboot
INFO:requests.packages.urllib3.connectionpool:Starting new HTTPS connection (1): review.coreboot.org
ERROR:root:The following commit needs to be pushed to coreboot.org:
ERROR:root:  Branch "kindred"
ERROR:root:  in directory "/mnt/host/source/src/third_party/coreboot"
ERROR:root:  with change-id "Ithischangeidwillnotbefoundbecauseitdoesntexist"
ERROR:root:Please push the branch to review.coreboot.org, and then re-start this program with --continue
(cr) $ cp testdata/need_to_upstream.yaml ~/.new_variant.yaml
(cr) $ ./new_variant.py --continue
INFO:root:Running step push_coreboot
INFO:root:Running step upload_CLs
INFO:root:Running step find_coreboot_upstream
ERROR:root:Program cannot continue until coreboot CL is upstreamed.
ERROR:root:(coreboot:32936, change-id Ichangeiddoesntmatterbecausewealreadyknowtheclnumber)
ERROR:root:Please wait for the CL to be upstreamed, then run this program again with --continue
(cr) $ cp testdata/upstreamed.yaml ~/.new_variant.yaml
(cr) $ ./new_variant.py --continue
INFO:root:Running step push_coreboot
INFO:root:Running step upload_CLs
INFO:root:Running step find_coreboot_upstream
INFO:root:Running step clean_up
```

Determining Cq-Depend
---------------------
The test data for Cq-Depend uses old commits for Kindred, and has a step\_list
that prevents the CLs from being modified or uploaded. The intent here is to
show that the Cq-Depend line is determined correctly for each CL that has
dependencies.

```
(cr) $ cp testdata/cqdepend.yaml ~/.new_variant.yaml
(cr) $ ./new_variant.py --continue --verbose
INFO:root:Running step calc_cq_depend
DEBUG:root:Processing add_priv_yaml to add dependencies
DEBUG:root:Add to commit add_priv_yaml Cq-Depend: chromium:1629121, chromium:1638243, chrome-internal:1364967, chromium:1648602
DEBUG:root:Processing add_pub_yaml to add dependencies
DEBUG:root:Add to commit add_pub_yaml Cq-Depend: chrome-internal:1331261, chromium:1638243, chrome-internal:1364967, chromium:1648602
DEBUG:root:Processing cb_config to add dependencies
DEBUG:root:Add to commit cb_config Cq-Depend: chromium:1641906
(cr) $ rm ~/.new_variant.yaml
```

End-to-End Test
===============
`testdata/new_variant_fulltest.sh` is an end-to-end test of `new_variant.py`.
The script takes the name of a reference board as a parameter, and creates a
new variant of that reference board. The script ensures that `new_variant.py`
will not upload the CLs for the new variant to gerrit, so the script can be run
multiple times to test functionality.

The supported reference boards are:
* hatch
* puff
* volteer
* trembyle (zork)
* dalboz (zork)
* waddledee (dedede)
* waddledoo (dedede)

For example, to test that creating a variant of the Waddledee reference board
still works,

```
cd /mnt/host/source/src/platform/dev/contrib/variant/testdata
./new_variant_fulltest.sh waddledee
```

When the build finishes, all of the branches and commits for the new variant
will be `repo abandon`ed. The output at the end of a successful test looks
something like this:

```
[Lots of build messages not included here]

>>> Using system located in ROOT tree /build/dedede/

>>> No outdated packages were found on your system.
DEBUG:root:process returns 0
DEBUG:root:Symlink /build/dedede/etc/portage/package.mask/cros-workon already exists. Don't recreate it.
DEBUG:root:Symlink /build/dedede/etc/portage/package.unmask/cros-workon already exists. Don't recreate it.
DEBUG:root:Symlink /build/dedede/etc/portage/package.keywords/cros-workon already exists. Don't recreate it.
INFO:root:Stopped working on 'chromeos-base/chromeos-config-bsp-dedede-private chromeos-base/chromeos-ec sys-boot/coreboot-private-files-baseboard-dedede sys-boot/intel-jslfsp sys-boot/coreboot sys-boot/libpayload chromeos-base/vboot_reference sys-boot/depthcharge' for 'dedede'
DEBUG:root:build_path = "/build/dedede/firmware"
INFO:root:Running step abort
DEBUG:root:Processing step cb_variant
INFO:root:Abandoning branch coreboot_kingitchy_20200904 in directory /mnt/host/source/src/third_party/coreboot
DEBUG:root:Run ['repo', 'abandon', 'coreboot_kingitchy_20200904', '.']
DEBUG:root:cwd = /mnt/host/source/src/third_party/coreboot
Abandoned branches:
coreboot_kingitchy_20200904| src/third_party/coreboot

DEBUG:root:process returns 0
DEBUG:root:Processing step cb_config
INFO:root:Abandoning branch create_kingitchy_20200904 in directory /mnt/host/source/src/third_party/chromiumos-overlay
DEBUG:root:Run ['repo', 'abandon', 'create_kingitchy_20200904', '.']
DEBUG:root:cwd = /mnt/host/source/src/third_party/chromiumos-overlay
Abandoned branches:
create_kingitchy_20200904| src/third_party/chromiumos-overlay

DEBUG:root:process returns 0
DEBUG:root:Processing step commit_fit
INFO:root:Abandoning branch create_kingitchy_20200904 in directory /mnt/host/source/src/private-overlays/baseboard-dedede-private
DEBUG:root:Run ['repo', 'abandon', 'create_kingitchy_20200904', '.']
DEBUG:root:cwd = /mnt/host/source/src/private-overlays/baseboard-dedede-private
Abandoned branches:
create_kingitchy_20200904| src/private-overlays/baseboard-dedede-private

DEBUG:root:process returns 0
DEBUG:root:Processing step ec_image
INFO:root:Abandoning branch create_kingitchy_20200904 in directory /mnt/host/source/src/platform/ec
DEBUG:root:Run ['repo', 'abandon', 'create_kingitchy_20200904', '.']
DEBUG:root:cwd = /mnt/host/source/src/platform/ec
Abandoned branches:
create_kingitchy_20200904| src/platform/ec

DEBUG:root:process returns 0
INFO:root:Running step clean_up
/mnt/host/source/src/platform/dev/contrib/variant /mnt/host/source/src/platform/dev/contrib/variant ~/trunk/src/platform/dev/contrib/variant
/mnt/host/source/src/platform/dev/contrib/variant ~/trunk/src/platform/dev/contrib/variant
/mnt/host/source/src/private-overlays/overlay-dedede-private/chromeos-base/chromeos-config-bsp-dedede-private /mnt/host/source/src/platform/dev/contrib/variant ~/trunk/src/platform/dev/contrib/variant
/mnt/host/source/src/platform/dev/contrib/variant ~/trunk/src/platform/dev/contrib/variant
/mnt/host/source/src/project/dedede /mnt/host/source/src/platform/dev/contrib/variant ~/trunk/src/platform/dev/contrib/variant
/mnt/host/source/src/platform/dev/contrib/variant ~/trunk/src/platform/dev/contrib/variant
/mnt/host/source/src/private-overlays/baseboard-dedede-private/sys-boot/coreboot-private-files-baseboard-dedede/asset_generation/outputs /mnt/host/source/src/platform/dev/contrib/variant ~/trunk/src/platform/dev/contrib/variant
/mnt/host/source/src/platform/dev/contrib/variant ~/trunk/src/platform/dev/contrib/variant
(cr) $
```

For boards that require a fitimage, `new_variant_fulltest.sh` will create a
fake fitimage for the new variant by copying the reference board's fitimage.
Obviously this won't be bootable, but since the purpose is just to ensure that
the build works, this is OK, and prevents the tester from having to create the
fitimage outside the chroot (by running `gen_fit_image.sh`) and then restarting
`new_variant.py`.

Similarly, for boards that use the project configuration repositories (all
of the boards this test supports except for Hatch), `new_variant_fulltest.sh`
creates a configuration directory that will suffice for building, but it is not
an actual repo.

When `new_variant_fulltest.sh` is done, it will clean up the temporary files it
created and revert the changes it made to checked-in files.

Work-in-Progress
----------------

The scripts that create new CLs use `repo start`, which will begin a new branch
off of `m/master`. This is almost always what we want to do, except when we
don't. For example, if you are editing the coreboot template files (in
`third_party/coreboot/util/mainboard/google`) on a branch, when
`create_coreboot_variant.sh` runs, it will start a new branch based on
`m/master` and the changes you had on your branch will not be visible. The
script will copy the previous versions of the files (from `m/master`) without
your updates. This same problem can happen with the EC baseboard sources that
are copied to make a new variant, or when fixing bugs in the private fitimage
scripts.

To force the scripts to use `HEAD` instead of `m/master` as the basis for a
new branch, set `NEW_VARIANT_WIP=1` in the environment:

```
NEW_VARIANT_WIP=1 ./new_variant_fulltest.sh waddledoo
```

When the branches are abandoned as part of clean-up, your repo will go back
to `m/master`, so you will need to manually `git checkout` the branch where
you were making changes.
