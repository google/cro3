# Copyright 2023 The ChromiumOS Authors
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

#
# bash completion script for lium
#
# return 0(OK) if given argument is already used
__lium_arg_used() { # arg
  local i=0
  while [ $i -lt "$COMP_CWORD" ]; do
    test "${COMP_WORDS[i]}" = "$1" && return 0
    i=$((i+1))
  done
  return 1
}

# return 0 (OK) if one of given arguments is already used
_lium_arg_used() { # arg [arg...]
  while [ "$#" -ne 0 ]; do
    __lium_arg_used "$1" && return 0
    shift 1
  done
  return 1
}

# return 0 if carg is included in the rest of args
_lium_arg_included() { # carg [args...]
  local cur=$1
  shift 1
  while [ "$#" -ne 0 ]; do
    test "${cur}" = "$1" && return 0
    shift 1
  done
  return 1
}

_lium_current_repo() {
  local i=0
  while [ $i -lt "$COMP_CWORD" ]; do
    if [ "${COMP_WORDS[i]}" = "--repo" ]; then
      i=$((i+1))
      echo "${COMP_WORDS[i]}"
      return
    fi
    i=$((i+1))
  done
  if [ -d "$PWD/.repo" ] && [ -d "$PWD/chroot" ]; then
    echo "$PWD"
  fi
}

_lium_get_duts() {
  ${COMP_WORDS[0]} dut list --ids 2>/dev/null
}

_lium_get_tests() {
  ${COMP_WORDS[0]} tast list --cached 2>/dev/null | cut -f 1 -d,
}

_lium_get_servos() {
  ${COMP_WORDS[0]} servo list --serials 2>/dev/null | cut -f 1
}

_lium_get_packages() {
  ${COMP_WORDS[0]} packages list --cached 2>/dev/null | cut -f 1
}

_lium_get_boards() {
  ${COMP_WORDS[0]} board list --cached 2>/dev/null | cut -f 1
}

_lium_get_branches() {
  ${COMP_WORDS[0]} config show android_branches 2>/dev/null | sed -e 's/[]["]//g' | sed -e 's/,/ /g'  
}

_lium_get_dut_actions() {
  lium dut 'do' --list-actions 2>/dev/null
}

_lium_comp_fs() { # option(-d|-f) current
  local DIR
  DIR=$(compgen "${1}" "${2}")
  if [ "$(echo "${DIR}" | wc -w)" = 1 ] && [ -d "${DIR}" ]; then
    compgen "${1}" "${DIR}/"
  else
    compgen "${1}" "${2}"
  fi
}

_lium_current_command() {
  local i=0
  while [ $i -lt "$COMP_CWORD" ]; do
    case "${COMP_WORDS[i]}" in
      -*) i=$COMP_CWORD;;
      *)
        echo "${COMP_WORDS[i]} ";;
    esac
    i=$((i+1))
  done
}

_lium_get_options() { # current
  local cmd
  local otype
  local a b
  cmd=$(_lium_current_command)
  otype=0

  ${cmd} --help 2>/dev/null | awk '/^..[^ ]/{print $0}' | while read -r a b ;do
    case ${a} in
      Positional) otype=1;;
      Options:) otype=2;;
      Commands:) otype=3;;
      -*)
        # All options start with '-'.
        if [ ${otype} -eq 2 ]; then
          _lium_arg_used "${a}" || echo "${a}"
        fi;;
      *)
        # Positional arguments must be converted.
        if [ ${otype} -eq 1 ]; then
          case "${a}" in
          dut|duts)
            _lium_get_duts;;
          actions)
            _lium_get_dut_actions;;
          tests)
            _lium_get_tests;;
          packages)
            _lium_get_packages;;
          files)
            if [ "${1#-}" == "${1}" ]; then
              _lium_comp_fs -f "${1}"
            fi;;
          esac
        # Subcommands must be shown as it is.
        elif [ ${otype} = 3 ]; then
          echo "${a}"
        fi
        ;;
    esac
  done
}

_lium() { # command current prev
  local cur=$2
  local prev=$3
  local dir_opts="--dir --dest --cros --arc"
  local file_opts="--image"
  local todo_opts="--version --workon"
  local servo_serial_opts="--serial --servo"

  COMPREPLY=( )
  # If there is --help option, no more options available.
  if _lium_arg_used "--help"; then
    return 0
  fi

  if _lium_arg_included "${prev}" "${todo_opts}"; then
    # TODO: support completion for each options. currently it is stopped.
    return 0
  elif [ "$prev" = "--dut" ]; then
	  echo "hoge" >&2
    IFS=" " read -r -a COMPREPLY <<< "$(compgen -W $(_lium_get_duts) -- $cur)"
  elif [ "$prev" = "--board" ]; then
    IFS=" " read -r -a COMPREPLY <<< "$(compgen -W "$(_lium_get_boards)" -- "$cur")"
  elif [ "$prev" = "--branch" ]; then 
    IFS=" " read -r -a COMPREPLY <<< "$(compgen -W "$(_lium_get_branches)" -- "$cur")"
  elif _lium_arg_included "${prev}" "${servo_serial_opts}"; then
    IFS=" " read -r -a COMPREPLY <<< "$(compgen -W "$(_lium_get_servos)" -- "$cur")"
  elif [ "$prev" = "--remove" ] && [ "${COMP_WORDS[1]}" = "dut" ] && [ "${COMP_WORDS[2]}" = "list" ]; then
    local DUTS
    DUTS=$(_lium_get_duts)
    IFS="\n" read -r -a COMPREPLY <<< "$(compgen -W "${DUTS}" -- "$cur")"
  elif _lium_arg_included "${prev}" "${dir_opts}"; then
    IFS=" " read -r -a COMPREPLY <<< "$(_lium_comp_fs -d "${cur}")"
  elif _lium_arg_included "${prev}" "${file_opts}"; then
    IFS=" " read -r -a COMPREPLY <<< "$(_lium_comp_fs -f "${cur}")"
  else
    local OPTS
    IFS="\n" read -r -a OPTS <<< "$(_lium_get_options "${cur}")"
    IFS=" " read -r -a COMPREPLY <<< "$(compgen -W ${OPTS} -- "${cur}")"
  fi
}

complete -F _lium lium
