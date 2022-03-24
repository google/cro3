#!/bin/bash -e

# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This script quickly builds the cros-test executable or its unit tests within a
# Chrome OS chroot.

# Personal Go workspace used to cache compiled packages.
readonly GOHOME="${HOME}/go"

# Directory where compiled packages are cached.
readonly PKGDIR="${GOHOME}/pkg"

# Go workspaces containing the Test Execution Service source.
SCRIPTDIR=$(realpath $0)
readonly SRCDIRS=$(dirname ${SCRIPTDIR})

# Package to build to produce cros-test
readonly CROS_TEST_PKG="chromiumos/test/execution/cmd/cros-test"
readonly CROS_PROVISION_PKG="chromiumos/test/provision/cmd/cros-provision"

# Output filename for cros-test executable.
readonly CROS_TEST_OUT="${GOHOME}/bin/cros-test"
readonly CROS_PROVISION_OUT="${GOHOME}/bin/cros-provision"

# Packages to exclude
readonly EXCLUDE_PKGS=(
	# TODO: re-enable after b/227254754 is fixed.
	"chromiumos/test/publish/cmd/publishserver/tests"
)

# Readonly Go workspaces containing source to build. Note that the packages
# installed to /usr/lib/gopath (dev-go/crypto, dev-go/subcommand, etc.) need to
# be emerged beforehand.
export GOPATH="$(IFS=:; echo "${SRCDIRS[*]}"):/usr/lib/gopath"
export GO111MODULE=off

# Disable cgo and PIE on building Test Service binaries. See:
# https://crbug.com/976196
# https://github.com/golang/go/issues/30986#issuecomment-475626018
export CGO_ENABLED=0
export GOPIE=0

readonly CMD=$(basename "${0}")

# Prints usage information and exits.
usage() {
  cat - <<EOF >&2
Quickly builds the cros-test executable or its unit tests.

Usage: ${CMD}                             Builds cros-test to ${CROS_TEST_OUT}.
       ${CMD} -b <pkg> -o <path>          Builds <pkg> to <path>.
       ${CMD} [-v] -T                     Tests all packages.
       ${CMD} [-v] [-r <regex>] -t <pkg>  Tests <pkg>.
       ${CMD} -C                          Checks all code using "go vet".
       ${CMD} -c <pkg>                    Checks <pkg>'s code.

EOF
  exit 1
}

# Prints all checkable packages.
get_check_pkgs() {
  local dir
  for dir in "${SRCDIRS[@]}"; do
    if [[ -d "${dir}/src" ]]; then
      (cd "${dir}/src"
       find . -name '*.go' | xargs dirname | sort | uniq | cut -b 3-)
    fi
  done
}

# Prints all packages with unit tests.
get_pkgs_with_unit_tests() {
  local dir
  for dir in "${SRCDIRS[@]}"; do
    if [[ -d "${dir}/src" ]]; then
      (cd "${dir}/src"
       find . -name '*_test.go' | xargs dirname | sort | uniq | cut -b 3-)
    fi
  done
}

# Prints all testable packages.
get_test_pkgs() {
  local pkgs=$(get_pkgs_with_unit_tests)
  for pkg in ${pkgs}; do
    if [[ ! "${EXCLUDE_PKGS[*]}" =~ "${pkg}" ]]; then
      echo "${pkg}"
    fi
  done
}

# Builds an executable package to a destination path.
run_build() {
  local pkg="${1}"
  local dest="${2}"
  go build -i -pkgdir "${PKGDIR}" -o "${dest}" "${pkg}"
}

# Checks one or more packages.
run_vet() {
  go vet -unusedresult.funcs=errors.New,errors.Wrap,errors.Wrapf,fmt.Errorf,\
fmt.Sprint,fmt.Sprintf,sort.Reverse \
    -printf.funcs=Log,Logf,Error,Errorf,Fatal,Fatalf,Wrap,Wrapf "${@}"
}

# Tests one or more packages.
run_test() {
  local args=("${@}" "${EXTRAARGS[@]}")
  go test ${verbose_flag} -pkgdir "${PKGDIR}" \
     ${test_regex:+"-run=${test_regex}"} "${args[@]}"
}

# Executable package to build.
build_pkg=

# Path to which executable package should be installed.
build_out=

# Package to check via "go vet".
check_pkg=

# Test package to build and run.
test_pkg=

# Verbose flag for testing.
verbose_flag=

# Test regex list for unit testing.
test_regex=

while getopts "CTb:c:ho:r:t:v-" opt; do
  case "${opt}" in
    C)
      check_pkg=all
      ;;
    T)
      test_pkg=all
      ;;
    b)
      build_pkg="${OPTARG}"
      ;;
    c)
      check_pkg="${OPTARG}"
      ;;
    o)
      build_out="${OPTARG}"
      ;;
    r)
      test_regex="${OPTARG}"
      ;;
    t)
      test_pkg="${OPTARG}"
      ;;
    v)
      verbose_flag="-v"
      ;;
    *)
      usage
      ;;
  esac
done

shift $((OPTIND-1))
EXTRAARGS=( "$@" )

if [ -n "${build_pkg}" ]; then
  if [ -z "${build_out}" ]; then
    echo "Required output file missing: -o <path>" >&2
    exit 1
  fi
  run_build "${build_pkg}" "${build_out}"
elif [ -n "${test_pkg}" ]; then
  if [ "${test_pkg}" = 'all' ]; then
    run_test $(get_test_pkgs)
  else
    run_test "${test_pkg}"
  fi
elif [ -n "${check_pkg}" ]; then
  if [ "${check_pkg}" = 'all' ]; then
    run_vet $(get_check_pkgs)
  else
    run_vet "${check_pkg}"
  fi
else
  run_build "${CROS_TEST_PKG}" "${CROS_TEST_OUT}"
  run_build "${CROS_PROVISION_PKG}" "${CROS_PROVISION_OUT}"
fi
