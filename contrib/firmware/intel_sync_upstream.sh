#!/bin/bash
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

SOC_LIST=(tgl jsl adl)
declare -A SOC_EDK_LOCAL_DIR_MAP=( ["tgl"]="branch2-private" ["jsl"]="branch1-private" ["adl"]="branch1-private" )

function die()
{
  if [ $1 -ne 0 ]; then
    echo "Error: $1"
    echo "$2"
    exit -42
  fi;
}

function usage()
{
  echo "Error: missing parameter."
  echo "Usage: $0 SOC [fsp|edk2|edk2-platforms|coreboot] version_string"
  echo "Example: $0 tgl fsp 'TGL.2527_17'"
  exit -42
}

# Verify param count
if [ "$#" -ne "3" ]; then
  usage
fi;
SOC="$1"
DIR="$2"
VERSION="$3"

if [[ ! "${SOC_LIST[*]}" =~ ${SOC} ]]; then
  die 1 "SoC is not supported"
fi

case $DIR in
  fsp)
    STAGING_PREFIX=${SOC}
    CHROMEOS_BRANCH=chromeos
    SRC_DIR="${CHROMIUM_TOT_ROOT}/src/third_party/fsp/${SOC}/$DIR/$LOCAL_DIR"
    STAGING_REPO="https://chrome-internal.googlesource.com/chromeos/third_party/intel-fsp/${STAGING_PREFIX}-staging"
    ;;

  edk2 | edk2-platforms)
    STAGING_PREFIX=$DIR
    LOCAL_DIR="${SOC_EDK_LOCAL_DIR_MAP[${SOC}]}"
    CHROMEOS_BRANCH=chromeos-${SOC}-$LOCAL_DIR
    SRC_DIR="${CHROMIUM_TOT_ROOT}/src/third_party/fsp/${SOC}/$DIR/$LOCAL_DIR"
    STAGING_REPO="https://chrome-internal.googlesource.com/chromeos/third_party/intel-fsp/${STAGING_PREFIX}-staging"
    ;;

  coreboot)
    STAGING_PREFIX=${SOC}
    CHROMEOS_BRANCH=chromeos
    SRC_DIR="${CHROMIUM_TOT_ROOT}/src/third_party/coreboot-intel-private/${SOC}"
    STAGING_REPO="https://chrome-internal.googlesource.com/chromeos/third_party/coreboot-intel-private/${STAGING_PREFIX}-staging"
    ;;

  *)
    usage
    ;;
esac

case ${VERSION} in
  master | EDK2_Trunk_Intel | main)
    UPREV_BRANCH=remotes/${STAGING_PREFIX}-staging/upstream/${VERSION}
    ;;

  *)
    UPREV_BRANCH=upstream/${VERSION}
    ;;
esac

if [ -z "${CHROMIUM_TOT_ROOT}" ]; then
  die 1 "CHROMIUM_TOT_ROOT environment variable is not set"
  exit -1
fi

# Clone the repo where the staging changes need to be pushed
pushd "$SRC_DIR" > /dev/null
die $? "Can't find $SRC_DIR"

# Add staging repo as remote repo to my local repo
git remote add ${STAGING_PREFIX}-staging "$STAGING_REPO"
err=$?

# If remote already exists, that's ok, but otherwise, exit on error
if [ $err -ne 0 ] && [ $err -ne 128 ]; then
  die $err "Can't add remote ${STAGING_PREFIX}-staging"
elif [ $err -eq 0 ]; then
  echo "Created remote ${STAGING_PREFIX}-staging"
else
  echo "Remote ${STAGING_PREFIX}-staging already exists"
fi;

git fetch --tags --force ${STAGING_PREFIX}-staging
die $? "Can't fetch ${STAGING_PREFIX}-staging"

# Detach from any branch before deleting
git checkout --detach

# Removing a stale branch
git branch -D ${STAGING_PREFIX}-staging-${VERSION}

# Set up remote branch
git checkout ${UPREV_BRANCH} -b ${STAGING_PREFIX}-staging-${VERSION}
die $? "Can't checkout upstream/${VERSION}"
echo "Checked out upstream/${VERSION} to branch ${STAGING_PREFIX}-staging-${VERSION}"

echo "Pushing to a staging repo to avoid 'forge commiter' permission issues"
git push -o skip-validation cros-internal HEAD:refs/heads/staging/${STAGING_PREFIX}-${VERSION}
die $? "Could not push to a staging repo"

# Checkout a local branch from remotes/cros-internal/${CHROMEOS_BRANCH}
git branch -D chrome-internal-tot
git checkout -b chrome-internal-tot cros-internal/${CHROMEOS_BRANCH}
die $? "Error checking out cros-internal/${CHROMEOS_BRANCH}"
echo "Checked out cros-internal/${CHROMEOS_BRANCH} to branch chrome-internal-tot"

# Merge from staging branch
git merge ${STAGING_PREFIX}-staging-${VERSION} --strategy-option theirs --no-ff --log
if [ $? -ne 0 ]; then
  echo "Didn't merge cleanly to ${STAGING_PREFIX}-staging-${VERSION}"

  while true
  do
    read -r -p "Do you want to force sync to the tag? [y/n] >" input

    case $input in
      [yY][eE][sS]|[yY])
        echo "Force syncing"
        # Remove all the changes that were not in the tag
        git diff --name-only --diff-filter=U | xargs git rm

        # Clean any temporary files
        git clean -fx

        # No signoff used in FSP repo
        git commit

        git diff -a chrome-internal-tot..${STAGING_PREFIX}-staging-${VERSION} > /tmp/merge-to-tag.patch
        patch -p1 < /tmp/merge-to-tag.patch
        rm /tmp/merge-to-tag.patch
        git add .
        git commit --amend --no-edit

        break
        ;;

      [nN][oO]|[nN])
        echo "Launching mergetool to manually fix issues."
        git mergetool
        die $? "Error returned from mergetool"
        git commit
        break
        ;;
      *)
        echo "Invalid input..."
        ;;
    esac
  done
fi;
echo "Merge of ${STAGING_PREFIX}-staging-${VERSION} complete, ready for upload."

while true
do
  read -r -p "Do you want to push your changes to cros-internal? [y/n] >" input

  case $input in
    [yY][eE][sS]|[yY])
      git push cros-internal HEAD:refs/for/${CHROMEOS_BRANCH}
      echo "Pushed merge of ${STAGING_PREFIX}-staging-${VERSION}, ready for review."
      break
      ;;

    [nN][oO]|[nN])
      echo "Ready to push merge of ${STAGING_PREFIX}-staging-${VERSION}."
      echo "Execute 'git push cros-internal HEAD:refs/for/${CHROMEOS_BRANCH}' to push change."
      break
      ;;

    *)
      echo "Invalid input..."
      ;;
  esac
done
