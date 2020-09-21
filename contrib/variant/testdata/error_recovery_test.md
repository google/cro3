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

## fw_build_config.sh

`fw_build_config.sh` is not tested here. Because of the scripts use `repo`
and `git` commands, it is not sufficient to create a directory with the
required files.

## Hatch add_variant.sh

Perform the test in
`/mnt/host/source/src/private-overlays/overlay-hatch-private/chromeos-base/chromeos-config-bsp-hatch-private`.

For each test case, run `add_variant.sh tiamat`

Add `false` at the following places in the script:
* before `sed`
* before `cat`
* before `git add`
* before `git commit`
* after `git commit`

Check the local directory to ensure the branch has been deleted and no changes
or new files are left.

## Hatch fitimage

Perform the test in
`/mnt/host/source/src/private-overlays/baseboard-hatch-private/sys-boot/coreboot-private-files-hatch/files`.

For each test case, run `add_fitimage.sh tiamat`

Add `false` at the following places in `add_fitimage.sh`:
* before `sed`
* before `git add`
* before `git commit`
* after `git commit`

Check the local directory to ensure the branch has been deleted and no changes
or new files are left.

With `add_fitimage.sh` succeeding now, for each test case, run
```
./add_fitimage.sh tiamat
cp files/fitimage-hatch.bin ../asset_generation/outputs/fitimage-tiamat.bin
cp files/fitimage-hatch-versions.txt ../asset_generation/outputs/fitimage-tiamat-versions.txt
echo test >> ../asset_generation/outputs/fit.log
./commit_fitimage.sh tiamat
```

Add `false` at the following places in `commit_fitimage.sh`:
* before each of the two `cp` commands
* before each of the three `git add` commands
* before `git commit`
* after `git commit`

Check the local directory to ensure the branch has been deleted and no changes
or new files are left.

## Volteer fitimage

Perform the test in
`/mnt/host/source/src/private-overlays/baseboard-volteer-private/sys-boot/coreboot-private-files-baseboard-volteer/files`.

For each test case, run `add_fitimage.sh gnastygnorc`

Add `false` at the following places in `add_fitimage.sh`:
* before `cp`
* before `git add` for the CSV file
* before `sed`
* before `git add`
* before `git commit`
* after `git commit`

Check the local directory to ensure the branch has been deleted and no changes
or new files are left.

With `add_fitimage.sh` succeeding now, for each test case, run
```
./add_fitimage.sh gnastygnorc
cp fitimage-volteer.bin ../asset_generation/outputs/fitimage-gnastygnorc.bin
cp fitimage-volteer-versions.txt ../asset_generation/outputs/fitimage-gnastygnorc-versions.txt
cp ../asset_generation/outputs/fit-volteer.log ../asset_generation/outputs/fit-gnastygnorc.log
cp blobs/descriptor-volteer.bin blobs/descriptor-gnastygnorc.bin
cp blobs/csme-volteer.bin blobs/csme-gnastygnorc.bin
./commit_fitimage.sh gnastygnorc
```

Add `false` at the following places in `commit_fitimage.sh`:
* before each of the two `cp` commands
* before each of the four `git add` commands
* before `git commit`
* after `git commit`

Check the local directory to ensure the branch has been deleted and no changes
or new files are left.

## Dedede fitimage

Perform the test in
`/mnt/host/source/src/private-overlays/baseboard-dedede-private/sys-boot/coreboot-private-files-baseboard-dedede/files`.

For each test case, run `add_fitimage.sh kingitchy`

Add `false` at the following places in `add_fitimage.sh`:
* before `sed`
* before `git add`
* before `git commit`
* after `git commit`

Check the local directory to ensure the branch has been deleted and no changes
or new files are left.

With `add_fitimage.sh` succeeding now, for each test case, run
```
./add_fitimage.sh kingitchy
cp blobs/fitimage-waddledee.bin ../asset_generation/outputs/fitimage-kingitchy.bin
cp blobs/fitimage-waddledee-versions.txt ../asset_generation/outputs/fitimage-kingitchy-versions.txt
echo test >> ../asset_generation/outputs/fit.log
./commit_fitimage.sh kingitchy
```

Add `false` at the following places in `commit_fitimage.sh`:
* before each of the two `cp` commands
* before each of the three `git add` commands
* before `git commit`
* after `git commit`

Check the local directory to ensure the branch has been deleted and no changes
or new files are left.

## Puff fitimage

Perform the test in
`/mnt/host/source/src/private-overlays/bbaseboard-puff-private/sys-boot/coreboot-private-files-puff/files`.

For each test case, run `add_fitimage.sh tiamat`

Add `false` at the following places in `add_fitimage.sh`:
* before `sed`
* before `git add`
* before `git commit`
* after `git commit`

Check the local directory to ensure the branch has been deleted and no changes
or new files are left.

With `add_fitimage.sh` succeeding now, for each test case, run
```
./add_fitimage.sh tiamat
cp fitimage-puff.bin ../asset_generation/outputs/fitimage-tiamat.bin
cp fitimage-puff-versions.txt ../asset_generation/outputs/fitimage-tiamat-versions.txt
./commit_fitimage.sh tiamat
```

Add `false` at the following places in `commit_fitimage.sh`:
* before each of the two `cp` commands
* before each of the two `git add` commands
* before `git commit`
* after `git commit`

Check the local directory to ensure the branch has been deleted and no changes
or new files are left.
