#!/bin/bash -e
VARS_USED="$(cat docs/cmdline.md | grep -o -E '\$\{?[_A-Z]{1,}\}?' | tr -d '{' | tr -d '}' | tr -d '$' | sort -u)"
VARS_EXPLAINED="$(cat docs/cmdline_preface.md | grep -o -E '\$\{?[_A-Z]{1,}\}?' | tr -d '{' | tr -d '}' | tr -d '$' | sort -u)"

if [ $"VARS_USED" != $"VARS_EXPLAINED" ]; then
	echo "----"
	echo "# VARS_USED:"
	echo "${VARS_USED}"
	echo "----"
	echo "# VARS_EXPLAINED:"
	echo "${VARS_EXPLAINED}"
	echo "----"
	echo "Variables appeared in docs/cmdline.md and docs/cmdline_preface.md did not match. Please fix by editing those files."
	exit 1
fi
