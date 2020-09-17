# Test error recovery in shell scripts

To test the error recovery functions in the various shell scripts, add
`false` in various places to induce failure and observe that everything
is cleaned up.

## add_variant_to_yaml.sh

For each test case, run `add_variant_to_yaml.sh hatch tiamat`

Add `false` at the following places in the script:
* before `revbump_ebuild`
* before `git add "${YAML}"`
* before `git commit`
* after `git commit`

Check `/mnt/host/source/src/overlays` to ensure the branch has been deleted
and no changes or new files are left.

## copy_cras_config.sh (zork only)

For each test case, run `copy_cras_config.sh zork trembyle grue`

Add `false` at the following places in the script:
* before `revbump_ebuild`
* before `mkdir`
* before `cp`
* before `git add`
* before `git commit`
* after `git commit`

Check `/mnt/host/source/src/overlays` to ensure the branch has been deleted
and no changes or new files are left.

## create_coreboot_config.sh

For each test case, run `create_coreboot_config.sh hatch hatch tiamat`

Add `false` at the following places in the script:
* before `sed`
* before `git add`
* before `git commit`
* after `git commit`

Check `/mnt/host/source/src/third_party/chromiumos-overlay` to ensure the
branch has been deleted and no changes or new files are left.

## create_coreboot_variant.sh

For each test case, run `CB_SRC_DIR=/mnt/host/source/src/third_party/coreboot
create_coreboot_variant.sh hatch hatch tiamat`

Add `false` at the following places in the script:
* before `kconfig.py`
* before `mv`
* before `git add`
* before `git commit`
* after `git commit`

Check `/mnt/host/source/src/third_party/coreboot` to ensure the branch has been
deleted and no changes or new files are left.

## create_initial_ec_image.sh

For each test case, run `create_initial_ec_image.sh hatch tiamat`

Add `false` at the following places in the script:
* before `mkdir`
* before `cp`
* before `find`
* before `make`
* before `git add`
* before `git commit`
* after `git commit`

Check `/mnt/host/source/src/platform/ec/board` to ensure the branch has been
deleted and no changes or new files are left.

## Others

`fw_build_config.sh` is not tested here. Because of the scripts use `repo`
and `git` commands, it is not sufficient to create a directory with the
required files.

The private scripts (mainly `add_variant.sh` in
`private-overlays/baseboard-hatch-private`) will have separate test
instructions.
