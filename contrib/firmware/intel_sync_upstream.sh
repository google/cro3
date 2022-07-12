#!/bin/bash
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

SOC_LIST=(tgl jsl adl adln mtl)
declare -A SOC_EDK_LOCAL_DIR_MAP=( ["tgl"]="branch2-private" ["jsl"]="branch1-private" ["adl"]="branch1-private" ["adln"]="branch1-private" ["mtl"]="branch1-private" )

# If FSP is using a staging repo that does not follow the format ${SOC}-staging,
# then add the mapping here.
declare -A SOC_FSP_STAGING_REPO_MAP=( ["adl"]="ccg-adl-generic-full" ["adln"]="adl-n-staging" ["mtl"]="mtl-staging")

# If edk2/edk2-platforms are using a branch prefix that does not follow the format chromeos-${SOC},
# then add the mapping here.
declare -A SOC_EDK_BRANCH_PREFIX_MAP=( ["adln"]="chromeos-adl-n" )

# If edk2/edk2-platforms are using a repo name with a suffix (e.g. are not edk-staging or edk-platforms-staging)
declare -A SOC_EDK_REPO_SUFFIX_MAP=( ["mtl"]="intelcollab" )

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
    if [ -v SOC_FSP_STAGING_REPO_MAP["${SOC}"] ]; then
        STAGING_NAME="${SOC_FSP_STAGING_REPO_MAP[${SOC}]}"
    else
        STAGING_NAME="${SOC}-staging"
    fi
    CHROMEOS_BRANCH=chromeos
    SRC_DIR="${CHROMIUM_TOT_ROOT}/src/third_party/fsp/${SOC}/$DIR/$LOCAL_DIR"
    STAGING_REPO="https://chrome-internal.googlesource.com/chromeos/third_party/intel-fsp/${STAGING_NAME}"
    ;;

  edk2 | edk2-platforms)
    if [ -v SOC_EDK_REPO_SUFFIX_MAP["${SOC}"] ]; then
      STAGING_NAME="${DIR}-staging-${SOC_EDK_REPO_SUFFIX_MAP[${SOC}]}"
    else
      STAGING_NAME="${DIR}-staging"
    fi
    LOCAL_DIR="${SOC_EDK_LOCAL_DIR_MAP[${SOC}]}"
    if [ -v SOC_EDK_BRANCH_PREFIX_MAP["${SOC}"] ]; then
      CHROMEOS_BRANCH="${SOC_EDK_BRANCH_PREFIX_MAP[${SOC}]}-${LOCAL_DIR}"
    else
      CHROMEOS_BRANCH="chromeos-${SOC}-${LOCAL_DIR}"
    fi
    SRC_DIR="${CHROMIUM_TOT_ROOT}/src/third_party/fsp/${SOC}/$DIR/$LOCAL_DIR"
    STAGING_REPO="https://chrome-internal.googlesource.com/chromeos/third_party/intel-fsp/${STAGING_NAME}"
    ;;

  coreboot)
    STAGING_NAME="${SOC}-staging"
    CHROMEOS_BRANCH=chromeos
    SRC_DIR="${CHROMIUM_TOT_ROOT}/src/third_party/coreboot-intel-private/${SOC}"
    STAGING_REPO="https://chrome-internal.googlesource.com/chromeos/third_party/coreboot-intel-private/${STAGING_NAME}"
    ;;

  *)
    usage
    ;;
esac

# Assumption is that the staging repo mirrors tags and heads under upstream/
case ${VERSION} in
  master | EDK2_Trunk_Intel | main)
    UPREV_BRANCH=remotes/${STAGING_NAME}/upstream/${VERSION}
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
git remote add ${STAGING_NAME} "$STAGING_REPO"
err=$?

# If remote already exists, that's ok, but otherwise, exit on error
if [ $err -ne 0 ] && [ $err -ne 3 ] && [ $err -ne 128 ]; then
  die $err "Can't add remote ${STAGING_NAME}"
elif [ $err -eq 0 ]; then
  echo "Created remote ${STAGING_NAME}"
else
  echo "Remote ${STAGING_NAME} already exists"
fi;

git fetch --tags --force ${STAGING_NAME}
die $? "Can't fetch ${STAGING_NAME}"

# Detach from any branch before deleting
git checkout --detach

# Removing a stale branch
git branch -D ${STAGING_NAME}-${VERSION}

# Set up remote branch
git checkout ${UPREV_BRANCH} -b ${STAGING_NAME}-${VERSION}
die $? "Can't checkout upstream/${VERSION}"
echo "Checked out upstream/${VERSION} to branch ${STAGING_NAME}-${VERSION}"

echo "Pushing to a staging repo to avoid 'forge commiter' permission issues"
git push -o skip-validation -o nokeycheck cros-internal HEAD:refs/heads/staging/${STAGING_PREFIX}-${VERSION}
die $? "Could not push to a staging repo"

# Checkout a local branch from remotes/cros-internal/${CHROMEOS_BRANCH}
git branch -D chrome-internal-tot
git checkout -b chrome-internal-tot cros-internal/${CHROMEOS_BRANCH}
die $? "Error checking out cros-internal/${CHROMEOS_BRANCH}"
echo "Checked out cros-internal/${CHROMEOS_BRANCH} to branch chrome-internal-tot"

# Merge from staging branch
git merge ${STAGING_NAME}-${VERSION} --strategy-option theirs --no-ff --log
if [ $? -ne 0 ]; then
  echo "Didn't merge cleanly to ${STAGING_NAME}-${VERSION}"

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

        git diff -a chrome-internal-tot..${STAGING_NAME}-${VERSION} > /tmp/merge-to-tag.patch
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
echo "Merge of ${STAGING_NAME}-${VERSION} complete, ready for upload."

while true
do
  read -r -p "Do you want to push your changes to cros-internal? [y/n] >" input

  case $input in
    [yY][eE][sS]|[yY])
      git push cros-internal HEAD:refs/for/${CHROMEOS_BRANCH}
      echo "Pushed merge of ${STAGING_NAME}-${VERSION}, ready for review."
      break
      ;;

    [nN][oO]|[nN])
      echo "Ready to push merge of ${STAGING_NAME}-${VERSION}."
      echo "Execute 'git push cros-internal HEAD:refs/for/${CHROMEOS_BRANCH}' to push change."
      break
      ;;

    *)
      echo "Invalid input..."
      ;;
  esac
done
