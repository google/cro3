#!/bin/bash

set -e

. src/cmd/cro3.bash

cro3() {
  if [ "$1" = "--help" -o "$1" = "help" ]; then
    cat << EOF
Usage: cro3 [options]

dummy cro3 for test

Options:
  --help show help

Commands:
  shibuya
  roppongi
EOF
  fi
}

test_complete() {
  _cro3 "${COMP_WORDS[0]}" "${COMP_WORDS[${COMP_CWORD}]}" "${COMP_WORDS[${COMP_CWORD}-1]}"
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

