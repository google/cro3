# New variant of Zork

[TOC]

Contact `chromeos-scale-taskforce@google.com` for questions.

This tutorial shows how to create the "Grue" variant of Zork's Trembyle
reference board.

The Zork baseboard has two reference boards: Trembyle and Dalboz. This example
will show creation of a variant of Trembyle, but the process for Dalboz is
identical except for the reference board name.

Zork uses the new per-project configuration repository (in
src/project/zork/${VARIANT}).

A new variant for Zork involves the following steps:
1. Build project configuration and verify new variant exists
2. Create coreboot variant
3. Create coreboot configuration
4. Create the CRAS (ChromeOS Audio Server) configuration
5. Create EC image
6. Build firmware image for new variant

## Per-project configuration repository

A gerrit administrator must create the project configuration repository before
you can begin the process to create a new variant of Zork. Please file a bug
to have the project configuration updated using
[go/cros-boxster-bug](go/cros-boxster-bug) or
https://b.corp.google.com/issues/new?component=167276&template=1022133.

This example shows how to create the "Grue" variant of the Trembyle
reference board. Note that there is no project configuration repository
for grue, but this example proceeds as if it does exist. See
[testdata/grue.md](../testdata/grue.md) for details of how to create this
repository for testing purposes.

## Create the new variant and upload the CLs

```
(cr) $ cd ~/trunk/src/platform/dev/contrib/variant
(cr) $ ./new_variant.py --board=trembyle --variant=grue --bug=b:12345
[... the project config builds (using emerge) ... ]
INFO:root:Running step fw_build_config
[... the project config is re-generated ...]
INFO:root:Running step create_coreboot_variant
[...]
INFO:root:Running step create_coreboot_config
[...]
INFO:root:Running step copy_cras_config
[...]
INFO:root:Running step create_initial_ec_image
[... the EC code builds just for this variant ...]
INFO:root:Running step ec_buildall
[... the EC code builds for all targets ...]
INFO:root:Running step emerge_all
[... the firmware boot image builds (using emerge) ...]
INFO:root:Running step push_coreboot
ERROR:root:The following commit needs to be pushed to coreboot.org:
[...]
```

## Push the coreboot CL

Push the coreboot CL by following one of the linked guides for pushing to
upstream coreboot. Assign reviewers for the coreboot CL and wait for
a Code-Review +2 and the CL to be merged.

## Upload the rest of the CLs

Run `./new_variant.py --continue` to find the coreboot CL and upload the rest
of the CLs.

```
INFO:root:Running step push_coreboot
INFO:root:Running step upload_CLs
INFO:root:Running step find_coreboot_upstream
ERROR:root:Program cannot continue until coreboot CL is upstreamed.
[...]
```

## Add Cq-Depend information, re-upload, and clean up

After the coreboot CL has been merged, there will be an UPSTREAM CL to bring
it into the chromiumos tree. Run `./new_variant.py --continue` to find the
UPSTREAM CL, add Cq-Depend to the CLs that need it, re-upload the changed
CLs, and clean up.

```
INFO:root:Running step find_coreboot_upstream
INFO:root:Running step calc_cq_depend
INFO:root:Running step add_cq_depend
INFO:root:Running step re_upload
INFO:root:Running step clean_up
```

## Using Dalboz as the reference board

Note that using Dalboz as the reference board only requires using
`--board=dalboz` instead of `--board=trembyle`:

```
./new_variant.py --board=dalboz --variant=grue --bug=b:12345
```
