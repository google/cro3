#!/bin/bash

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO: Convert this to python.

get_ctarget_from_board()
{
  local board="$1"
  local base_board=$(echo ${board} | cut -d '_' -f 1)
  local board_overlay=$(cros_overlay_list --board="$base_board" --primary_only)
  cat "$board_overlay/toolchain.conf"
}

get_atom_from_config()
{
  local gcc_path="$(gcc-config -B "$1")"
  equery b ${gcc_path} | head -n1
}

get_ctarget_from_atom()
{
  local atom="$1"
  echo "$atom" | sed -E 's|cross-([^/]+)/.*|\1|g'
}

copy_gcc_libs_helper()
{
  local target_location="$1"
  local file_path="$2"
  local dir_path=$(dirname "$file_path")
  info "Copying $file_path symlink and file to $target_location/$dir_path/."
  sudo mkdir -p "$target_location/$dir_path"
  sudo cp -a "$file_path" "$target_location/$dir_path/"
  sudo cp -a "$(readlink -f $file_path)" "$target_location/$dir_path/"
  local env_d_file="$target_location/etc/env.d/05gcc"
  info "Adding $dir_path to LDPATH in file $env_d_file"
  sudo mkdir -p $(dirname "$env_d_file")
  local line_to_add="LDPATH=\"$dir_path\""
  if ! grep -q "^$line_to_add$" "$env_d_file" &>/dev/null
  then
    echo "$line_to_add" | sudo_append "$env_d_file"
  fi
}

copy_gcc_libs()
{
  # TODO: Figure out a better way of doing this?
  local target_location="$1"
  local atom="$2"
  local libgcc_file=$(portageq contents / $atom | \
                      grep /libgcc_s.so$)
  local libstdcxx_file=$(portageq contents / $atom | \
                         grep /libstdc++.so)
  if [[ -z "$libgcc_file" || -z "$libstdcxx_file" ]]
  then
    error "Could not find libgcc_s.so/libstdcxx_s.so. Is\
          =$atom emerged properly?"
    return 1
  fi
  copy_gcc_libs_helper $target_location $libgcc_file
  copy_gcc_libs_helper $target_location $libstdcxx_file
  return 0
}

cros_gcc_config()
{
  sudo gcc-config "$1" || return $?

  # Return if we're not switching profiles.
  if [[ "$1" == -* ]]
  then
    return 0
  fi

  local atom=$(get_atom_from_config "$1")
  if [[ $atom != cross* ]]
  then
    warn "$atom is not a cross-compiler."
    warn "Therefore not adding its libs to the board roots."
    return 0
  fi

  # Now copy the lib files into all possible boards.
  local ctarget=$(get_ctarget_from_atom "$atom")
  for board_root in /build/*
  do
    local board=$(basename $board_root)
    local board_tc=$(get_ctarget_from_board $board)
    if [[ "${board_tc}" == "${ctarget}" ]]
    then
      copy_gcc_libs "$board_root" $atom
    fi
  done
}
