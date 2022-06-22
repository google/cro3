#!/bin/bash
# Copyright 2022 The ChromiumOS Authors.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e

INSTALL_DIR=~/lib/depot_tools
function print_help {
  cat <<END
Usage: install.sh [options]

Options:
 --dir|-d <path>    Path to directory where labtunnel is to be installed, which
                    should be in your \$PATH (default = '~/lib/depot_tools').
END
}

# Parse args.
while [[ $# -ge 2 ]]; do
  case $1 in
    --dir|-d)
      INSTALL_DIR="$2"
      shift 2
      ;;
    *)
      echo "Error: Invalid option '$1'"
      print_help
      exit 1
      break
      ;;
  esac
done
if [ $# -eq 1 ]; then
  if [ "$1" == "help" ]; then
    print_help
    exit
  fi
  echo "Error: Invalid option '$1'"
  print_help
  exit 1
fi

# Build executable from go project.
SCRIPT_DIR="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"
bash "${SCRIPT_DIR}/build.sh"
CMD_PATH="${SCRIPT_DIR}/go/bin/labtunnel"

# Create a link to the built executable in the install dir.
INSTALL_PATH="${INSTALL_DIR}/labtunnel"
if [ -L "${INSTALL_PATH}" ]; then
  unlink "${INSTALL_PATH}"
fi

ln -s "${CMD_PATH}" "${INSTALL_PATH}"
chmod +x "${INSTALL_PATH}"

echo "Successfully installed labtunnel to '${INSTALL_PATH}'"
