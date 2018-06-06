#!/bin/bash

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO: Convert this to python.

get_all_board_toolchains()
{
  cros_setup_toolchains --show-board-cfg="$1" | sed 's:,: :g'
}

get_ctarget_from_board()
{
  local all_toolchains=( $(get_all_board_toolchains "$@") )
  echo "${all_toolchains[0]}"
}

get_board_arch()
{
  local ctarget=$(get_ctarget_from_board "$@")

  # Ask crossdev what the magical portage arch is!
  local arch=$(eval $(crossdev --show-target-cfg "${ctarget}"); echo ${arch})
  if [[ -z ${arch} ]] ; then
    error "Unable to determine ARCH from toolchain: ${ctarget}"
    return 1
  fi

  echo "${arch}"
  return 0
}
