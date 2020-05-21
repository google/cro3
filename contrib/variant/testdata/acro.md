# Test creating a new variant of Waddledee or Waddledoo (Dedede)

This document describes the steps to test the process of creating a new
variant of the Waddledee or Waddledoo reference boards in the Dedede program.
Most of these steps are done inside the chroot environment.

## Create per-project config

Normally, a new variant would have a per-project configuration repo created
by the CrOS gerrit admins. For the purposes of this test, create a directory
and populate it as if the repo existed.

```
(cr) $ mkdir -p ~/trunk/src/project/dedede/acro
(cr) $ cd ~/trunk/src/project/dedede/acro
(cr) $ cp -r ~/trunk/src/project/dedede/waddledee .
```

### Edit src/project/dedede/acro/config.star

Change all occurences of Waddledee to Acro, respecting capitalization. There
are all-lowercase, all-uppercase, and initial-uppercase versions of the name
in the config.star file.

```
(cr) $ cd ~/trunk/src/project/dedede/acro
(cr) $ sed -i -e "s/waddledee/acro/g" -e "s/WADDLEDEE/ACRO/g" -e "s/Waddledee/Acro/g" config.star
```

### Generate the config

```
(cr) $ cd ~/trunk/src/project/dedede/acro
(cr) $ ~/trunk/src/config/bin/gen_config config.star
```

## Update the PROJECTS list

Add "acro" to the `PROJECTS` list in

`src/private-overlays/overlay-dedede-private/chromeos-base/chromeos-config-bsp-dedede-private/chromeos-config-bsp-dedede-private-9999.ebuild`


```
 PROJECTS=(
     "waddledoo"
     "waddledee"
     "jslrvp"
     "wheelie"
+    "acro"
 )
```

## Ensure CLs do not get uploaded

Insert the step 'quit' in waddledee.py after step_names.EMERGE, so that
the test CLs are not uploaded.

```
 step_list = [
     step_names.EC_IMAGE,
     step_names.EC_BUILDALL,
     step_names.EMERGE,
+    'quit',
     step_names.PUSH,
     step_names.UPLOAD,
     step_names.CALC_CQ_DEPEND,
     step_names.ADD_CQ_DEPEND,
     step_names.RE_UPLOAD,
     step_names.CLEAN_UP]
```

## Create the 'acro' variant

`(cr) $ ./new_variant.py --board=waddledee --variant=acro --bug=b:157183582`

The program begins by building the project configuration to ensure that the
variant is included. If this step fails, you may have forgotten to update
`chromeos-config-bsp-dedede-private-9999.ebuild`

After building the project configuration, the program creates the coreboot
variant, coreboot configuration, and the files needed for generating the
fitimage. The program asks the user to generate the fitimage outside the
chroot, and then the program exits.

### Waddledee vs. Waddledoo

These steps work equally well if the new variant is based on the Waddledoo
reference board. The command to start the creation would be:

`(cr) $ ./new_variant.py --board=waddledoo --variant=acro --bug=b:157183582`

The rest of the process is the same regardless of the reference board chosen.

## Generate the fitimage

Open a new terminal. Assuming that you have the correct version of Intel FIT
installed (currently version 13.50.0.7049, but this will likely change in
the future) in `~/TXE/JSL`, the command would be:

```
$ cd ~/chromiumos/src/private-overlays/baseboard-dedede-private/sys-boot/coreboot-private-files-baseboard-dedede/asset_generation
$ ./gen_fit_image.sh acro ~/TXE/JSL -b
```

## Continue the 'acro' variant creation

Switch back to the terminal in the chroot and run `new_variant.py` again
with the `--continue` option:

`(cr) $ ./new_variant.py --continue`

The program will successfully build the 'acro' firmware, and then stop with
an error that it doesn't understand the 'quit' step. That is the desired
behavior, as we don't want to upload these CLs.

## Clean up

`./new_variant.py --abort` to delete all of the commits.

`rm -R ~/trunk/src/project/dedede/acro` to delete the per-project config

Use `git restore` to discard changes to `chromeos-config-bsp-dedede-private-9999.ebuild`
