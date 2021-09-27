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
  #   $1:  Server name (as built/installed into /usr/bin on the chroot)
  #   $2:  Dockerfile path for the build
  #   $3:  (optional) chroot path
  #   $4:  (optional) tags
  #   $5+: (optional) labels
  [[ $# -lt 3 ]] && die "${FUNCNAME[0]}: Server name and Dockerfile path required"
  server_name="$1"; shift
  docker_file="$1"; shift
  chroot_arg="$1"; shift
  tags="$1"; shift

  # Aggregate rest of CLI arguments as labels into an array
  labels=( "$@" )

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

  readonly default_tag="local-${USER}"
  if [[ "$tags" == "" ]]; then
    echo "No tags specified, defaulting to: ${default_tag}"
    tags="${default_tag}"
  fi

  readonly registry_name="gcr.io"
  readonly cloud_project="chromeos-bot"
  readonly image_name="${server_name}"
  readonly image_path="${registry_name}/${cloud_project}/${image_name}"

  readonly server_name docker_file chroot_arg tags
}


build_image() {
  # @FUNCTION: build_image
  # @USAGE: Docker builds + uploads to the registry.
  # @DESCRIPTION:

  # Construct and execute build command
  args=(-f "${docker_file}")

  # Map tags into -t options
  IFS=,
  for tag in $tags; do
      echo "tag: ${tag}"
      args+=(-t "${image_path}:${tag}")
  done

  # Map labels into --label options
  for label in "${labels[@]}"; do
      echo "label: ${label}"
      args+=(--label "${label:Q}")
  done
  args+=("${build_context}")

  echo sudo docker build "${args[@]}"
  sudo docker build "${args[@]}"

  # Push image to register
  sudo docker login -u oauth2accesstoken -p "$(gcloud auth print-access-token)" "https://${registry_name}"
  sudo docker push --all-tags "${image_path}"
}


build_container_image(){
  # @FUNCTION: build_container_image
  # @USAGE: [server_name]
  # @DESCRIPTION:
  #
  # Args:
  #   $1:  Server name (as built/installed into /usr/bin on the chroot)
  #   $2:  Dockerfile path for the build
  #   $3:  (optional) chroot path
  #   $4:  (optional) tags
  #   $5+: (optional) labels
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
  #   $3:  (optional) chroot path
  #   $4:  (optional) tags
  #   $5+: (optional) labels
  validate "$@"

  readonly tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  cp "${chroot}/usr/bin/${server_name}" "${tmpdir}"

  readonly build_context="${tmpdir}"
  build_image
}
