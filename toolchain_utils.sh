#!/bin/bash

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO: Convert this to python.

get_ctarget_from_board()
{
  local board="$1"
  local base_board="$(echo $board | cut -d '_' -f 1)"
  local board_overlay="$(cros_overlay_list --board="$base_board"\
    --primary_only)"
  cat "$board_overlay/toolchain.conf"
}

is_number()
{
  echo "$1" | grep -q "^[0-9]\+$"
}

is_config_installed()
{
  gcc-config -l | cut -d" " -f3 | grep -q "$1$"
}

get_installed_atom_from_config()
{
  local gcc_path="$(gcc-config -B "$1")"
  equery b "$gcc_path" | head -n1
}

get_atom_from_config()
{
  echo "$1" | sed -E "s|(.*)-(.*)|cross-\1/gcc-\2|g"
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
  sudo cp -a "$file_path"* "$target_location/$dir_path/"
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
                         grep /libstdc++.so$)
  if [[ -z "$libgcc_file" || -z "$libstdcxx_file" ]]
  then
    error "Could not find libgcc_s.so/libstdcxx_s.so. Is\
          =$atom emerged properly?"
    return 1
  fi
  copy_gcc_libs_helper $target_location $libgcc_file
  copy_gcc_libs_helper $target_location $libstdcxx_file
  sudo ROOT="$target_location" env-update
  return 0
}

get_current_binutils_config()
{
  local ctarget="$1"
  binutils-config -l | grep "$ctarget" | grep "*" | awk '{print $NF}'
}

get_bfd_config()
{
  local ctarget="$1"
  binutils-config -l | grep "$ctarget" | grep -v "gold" | head -n1 | \
    awk '{print $NF}'
}

emerge_gcc()
{
  local atom="$1"
  local ctarget="$(get_ctarget_from_atom $atom)"
  mask_file="/etc/portage/package.mask/cross-$ctarget"
  moved_mask_file=0

  # Move the package mask file elsewhere.
  if [[ -f "$mask_file" ]]
  then
    temp_file="$(mktemp)"
    sudo mv "$mask_file" "$temp_file"
    moved_mask_file=1
  fi

  USE+=" multislot"
  if echo "$atom" | grep -q "gcc-4.6.0$"
  then
    old_binutils_config="$(get_current_binutils_config $ctarget)"
    bfd_binutils_config="$(get_bfd_config $ctarget)"
    if [[ "$old_binutils_config" != "$bfd_binutils_config" ]]
    then
      sudo binutils-config "$bfd_binutils_config"
    fi
  fi
  sudo ACCEPT_KEYWORDS="*" USE="$USE" emerge ="$atom"
  emerge_retval=$?

  # Move the package mask file back.
  if [[ $moved_mask_file -eq 1 ]]
  then
    sudo mv "$temp_file" "$mask_file"
  fi

  if [[ ! -z "$old_binutils_config" &&
        "$old_binutils_config" != "$(get_current_binutils_config $ctarget)" ]]
  then
    sudo binutils-config "$old_binutils_config"
  fi

  return $emerge_retval
}

# This function should only be called when testing experimental toolchain
# compilers. Please don't call this from any other script.
cros_gcc_config()
{
  # Return if we're not switching profiles.
  if [[ "$1" == -* ]]
  then
    sudo gcc-config "$1"
    return $?
  fi

  # cros_gcc_config can be called like:
  # cros_gcc_config <number> to switch config to that
  # number. In that case we should just try to switch to
  # that config and not try to install a missing one.
  if ! is_number "$1" && ! is_config_installed "$1"
  then
    info "Configuration $1 not found."
    info "Trying to emerge it..."
    local atom="$(get_atom_from_config "$1")"
    emerge_gcc "$atom" || die "Could not install $atom"
  fi

  sudo gcc-config "$1" || die "Could not switch to $1"

  local boards=$(get_boards_from_config "$1")
  local board
  for board in $boards
  do
    cros_install_libs_for_config "$board" "$1"
    emerge-"$board" --oneshot sys-devel/libtool
  done
}

get_boards_from_config()
{
  local atom=$(get_installed_atom_from_config "$1")
  if [[ $atom != cross* ]]
  then
    warn "$atom is not a cross-compiler."
    warn "Therefore not adding its libs to the board roots."
    return 0
  fi

  # Now copy the lib files into all possible boards.
  local ctarget="$(get_ctarget_from_atom "$atom")"
  for board_root in /build/*
  do
    local board="$(basename $board_root)"
    local board_tc="$(get_ctarget_from_board $board)"
    if [[ "${board_tc}" == "${ctarget}" ]]
    then
      echo "$board"
    fi
  done
}

cros_install_libs_for_config()
{
  local board="$1"
  local atom=$(get_installed_atom_from_config "$2")
  copy_gcc_libs /build/"$board" "$atom"
}
