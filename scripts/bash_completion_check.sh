#!/bin/bash

set -e

. src/cmd/cro3.bash

cro3() {
  if [ "$1" = "--help" ] || [ "$1" = "help" ]; then
    cat <<EOF
Usage: cro3 [options]

dummy cro3 for test

Options:
  --help show help
  --dut  show dut list

Commands:
  shibuya
  roppongi
  dut
  tast
EOF
  fi
  if [ "$*" = "dut list --ids" ]; then
    echo "dut1 dut2 dut3"
  fi

  if [ "$*" = "tast run --help" ]; then
    cat <<EOF
Usage: cro3 tast run <tests>

Get tast test for the target DUT

Positional Arguments:
  tests             test name or pattern

Options:
  --help            display usage information
EOF
  fi
  if [ "$*" = "tast list --cached" ]; then
    echo "dummy.Test.First"
    echo "dummy.Test.Second"
    echo "dummy.TestThird"
  fi
}

test_complete() {
  _cro3 "${COMP_WORDS[0]}" "${COMP_WORDS[${COMP_CWORD}]}" "${COMP_WORDS[${COMP_CWORD} - 1]}"
}

COMP_CWORD=1
COMP_WORDS=("cro3" "")
test_complete
echo "${COMPREPLY[@]}" | grep -wq "shibuya"
echo "${COMPREPLY[@]}" | grep -wq "roppongi"
echo "${COMPREPLY[@]}" | grep -wq "Commands" && exit 1

COMP_CWORD=1
COMP_WORDS=("cro3" "shi" "")
test_complete
test "${COMPREPLY[@]}" = "shibuya"

COMP_CWORD=3
COMP_WORDS=("cro3" "dut" "--dut" "")
test_complete
echo "${COMPREPLY[@]}" | grep -wq "dut1"
echo "${COMPREPLY[@]}" | grep -wq "dut2"
echo "${COMPREPLY[@]}" | grep -wq "dut5" && exit 1

COMP_CWORD=3
COMP_WORDS=("cro3" "tast" "run" "")
test_complete
echo "${COMPREPLY[@]}" | grep -wq "dummy.Test.First"
echo "${COMPREPLY[@]}" | grep -wq "dummy.Test.Second"
echo "${COMPREPLY[@]}" | grep -wq "dummy.Third" && exit 1
exit 0
