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
  #   $5:  (optional) output file for metadata
  #   $6+: (optional) labels
  [[ $# -lt 3 ]] && die "${FUNCNAME[0]}: Server name and Dockerfile path required"
  server_name="$1"
  docker_file="$2"
  chroot_arg="$3"
  tags="$4"
  output_path="$5"
  shift 5

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
  ntag=0
  IFS=,
  for tag in $tags; do
      ntag="$((ntag+1))"
      args+=(-t "${image_path}:${tag}")
  done

  # Map labels into --label options
  for label in "${labels[@]}"; do
      args+=(--label "${label:Q}")
  done
  args+=("${build_context}")

  echo sudo docker build "${args[@]}"
  sudo docker build "${args[@]}"

  # Push image to register
  sudo docker login -u oauth2accesstoken -p "$(gcloud auth print-access-token)" "https://${registry_name}"
  sudo docker push --all-tags "${image_path}"

  # write output if requested
  if [[ -n "$output_path" ]]; then
    local digest
    digest=$(docker inspect --format='{{index .RepoDigests 0}}' "$image_path:${tag[0]}" \
                 | cut -d: -f2 )

    cat <<EOF > "$output_path"
{
    "repository" : {
       "hostname": "$registry_name",
       "project" : "$cloud_project"
    },
    "name" : "$image_name",
    "digest" : "$digest",
    "tags" : [
EOF

    ii=0
    local tag_block=""
    IFS=,
    for tag in $tags; do
        tag_block+="      \"$tag\""

        ii="$((ii+1))"
        if [[ $ii -lt $ntag ]]; then
          tag_block+=",\n"
        fi
    done
    echo -e "${tag_block}" >> "$output_path"

    cat <<EOF >> "$output_path"
    ]
}
EOF
  fi
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
