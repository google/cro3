# Test creating a new variant of Trembyle (Zork)

This document describes the steps to test the process of creating a new
variant of the Trembyle reference board. All of these steps are done inside
the chroot environment.

## Create per-project config

Normally, a new variant would have a per-project configuration repo created
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

Add load() commands for brand_config and defaults:
```
 """Generates a ConfigBundle proto for the grue project."""

 load("//config/util/config_bundle.star", "config_bundle")
+load("//config/util/brand_config.star", "brand_config")
 load("//config/util/design.star", "design")
 load("//config/util/hw_topology.star", "hw_topo")
 load("//program/program.star", "program")
+load("//program/defaults.star", "defaults")

 _GRUE = "Grue"
```

Also, change`_FW_BUILD_CONFIG = None` to
`_FW_BUILD_CONFIG = defaults.firmware_build_config(_GRUE)`

### Generate the config

```
cd ~/trunk/src/project/zork/grue
~/trunk/src/config/bin/gen_config config.star
```

## Update the PROJECTS list

Add "grue" to the `PROJECTS` list in
`src/private-overlays/overlay-zork-private/chromeos-base/chromeos-config-bsp-zork-private/chromeos-config-bsp-zork-private-9999.ebuild`

```
 PROJECTS=(
        "ezkinil"
        "morphius"
        "trembyle"
+       "grue"
 )
```

## Ensure CLs do not get uploaded

Insert the step 'quit' in trembyle.py after step_names.EMERGE, so that
the test CLs are not uploaded.

```
 step_list = [
     step_names.EC_IMAGE,
     step_names.EC_BUILDALL,
     step_names.EMERGE,
+    'quit',
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

Use `git restore` to discard changes to `chromeos-config-bsp-zork-private-9999.ebuild`
