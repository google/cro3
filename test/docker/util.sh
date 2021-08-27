#!/bin/bash
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


readonly current_dir="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"

readonly chroot_default="${current_dir}/../../../../../chroot"


validate () {
  # @FUNCTION: validate
  # @USAGE: validates inputs to build_*
  # @DESCRIPTION:
  #
  # Args:
  #   $1: Server name (as built/installed into /usr/bin on the chroot)
  #   $2: Dockerfile path for the build
  #   $3: (optional) chroot path
  #   $4: (optional) build version
  [[ $# -lt 2 ]] && die "${FUNCNAME}: Server name and Dockerfile path required"
  readonly server_name="$1"
  readonly docker_file="$2"
  readonly chroot_arg="$3"
  readonly build_version_arg="$4"

  if [[ -e ${CHROOT_VERSION_FILE} ]]; then
    echo "Script must run outside the chroot since this depends on docker"
    exit 1
  fi

  chroot="${chroot_arg}"
  if [ -z "${chroot}" ]; then
    echo "No chroot specified, so defaulting to: ${chroot_default}"
    chroot="${chroot_default}"
  fi

  if [ ! -d "${chroot}" ]; then
    echo "chroot path does not exist: ${chroot}"
    exit 1
  fi

  readonly build_version_default="local-${USER}"
  build_version="${build_version_arg}"
  if [ -z "${build_version}" ]; then
    echo "No build_version specified, so defaulting to: ${build_version_default}"
    build_version="${build_version_default}"
  fi

  readonly registry_name="gcr.io"
  readonly cloud_project="chromeos-bot"
  readonly image_name="${server_name}"
  readonly image_path="${registry_name}/${cloud_project}/${image_name}"
}

build_image() {
  # @FUNCTION: build_image
  # @USAGE: Docker builds + uploads to the registry.
  # @DESCRIPTION:
  sudo docker build -f "${docker_file}" -t "${image_path}:${build_version}" "${build_context}"
  sudo docker login -u oauth2accesstoken -p "$(gcloud auth print-access-token)" "https://${registry_name}"
  sudo docker push "${image_path}":"${build_version}"
}

build_container_image(){
  # @FUNCTION: build_container_image
  # @USAGE: [server_name]
  # @DESCRIPTION:
  #
  # Args:
  #   $1: Server name (as built/installed into /usr/bin on the chroot)
  #   $2: Dockerfile path for the build
  #   $3: (optional) chroot path
  #   $4: (optional) build version
  validate "$@"
  readonly build_context=$(dirname "${docker_file}")
  build_image
  trap 'rm -rf "${build_context}"' EXIT
}



build_server_image() {
  # @FUNCTION: build_server_image
  # @USAGE: [server_name]
  # @DESCRIPTION:
  #
  # Args:
  #   $1: Server name (as built/installed into /usr/bin on the chroot)
  #   $2: Dockerfile path for the build
  #   $3: (optional) chroot path
  #   $4: (optional) build version
  validate "$@"

  readonly tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  cp "${chroot}/usr/bin/${server_name}" "${tmpdir}"

  readonly build_context="${tmpdir}"
  build_image
}
