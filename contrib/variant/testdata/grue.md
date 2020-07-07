# Test creating a new variant of Trembyle (Zork)

This document describes the steps to test the process of creating a new
variant of the Trembyle reference board. All of these steps are done inside
the chroot environment.

## Create project config

Normally, a new variant would have a project configuration repo created
by the CrOS gerrit admins. For the purposes of this test, create a directory
and populate it as if the repo existed.

```
(cr) $ mkdir -p ~/trunk/src/project/zork/grue
(cr) $ cd ~/trunk/src/config
(cr) $ sbin/gen_project  ~/trunk/src/config zork \
~/trunk/src/program/zork/ grue \
~/trunk/src/project/zork/grue
```

### Edit src/project/zork/grue/config.star

Update the `_FW_BUILD_CONFIG` setting:

```
-_FW_BUILD_CONFIG = None
+_FW_BUILD_CONFIG = program.firmware_build_config(_GRUE)
```

### Generate the config

```
(cr) $ cd ~/trunk/src/project/zork/grue
(cr) $ ~/trunk/src/config/bin/gen_config config.star
```

## Update the PROJECTS list

Add "grue" to the `PROJECTS` list in
`src/private-overlays/overlay-zork-private/chromeos-base/chromeos-config-bsp-zork-private/chromeos-config-bsp-zork-private-9999.ebuild`

```
 PROJECTS=(
     "berknip"
     "dalboz"
     "dirinboz"
     "ezkinil"
     "morphius"
     "trembyle"
     "vilboz"
     "woomax"
+    "grue"
 )
```

## Modify the automation step\_list

Edit trembyle.py to modify `step\_list` so that "grue" will build correctly,
and so that the CLs do not get uploaded.

Remove the FW_BUILD_CONFIG step. Insert a 'quit' in trembyle.py after EMERGE,
so that new_variant.py will fail with an "unknown step" error before it tries
to upload any CLs to coreboot or gerrit.

```
 step_list = [
     step_names.PROJECT_CONFIG,
-    step_names.FW_BUILD_CONFIG,
     step_names.CB_VARIANT,
     step_names.CB_CONFIG,
     step_names.CRAS_CONFIG,
     step_names.EC_IMAGE,
     step_names.EC_BUILDALL,
     step_names.EMERGE,
+    'quit',
     step_names.PUSH,
     step_names.FIND,
     step_names.UPLOAD,
     step_names.CALC_CQ_DEPEND,
     step_names.ADD_CQ_DEPEND,
     step_names.RE_UPLOAD,
     step_names.CLEAN_UP]
```

## Create the 'grue' variant

`./new_variant.py --board=trembyle --variant=grue`

The program should successfully build the 'grue' firmware, and then
stop with an error that it doesn't understand the 'quit' step.

## Clean up

`./new_variant.py --abort` to delete all of the commits.

`rm -R ~/trunk/src/project/zork/grue` to delete the per-project config

Use `git restore` in the appropriate directories to discard changes to
`chromeos-config-bsp-zork-private-9999.ebuild` and `trembyle.py`.
