#!/bin/bash -e
TAST_TESTS=$1
if ! [ -d "${TAST_TESTS}" ] ; then
	echo "Please specify the path to analyzer as the first arg."
	exit 1
fi
TAST_TESTS="$(readlink -f "$(git -C "${TAST_TESTS}" rev-parse --show-toplevel)")"
git -C ${TAST_TESTS} remote -v | grep 'https://chromium.googlesource.com/chromiumos/platform/tast-tests' || {
	echo "it seems ${TAST_TESTS}" is not a tast-tests dir...
	exit 1
}
if ! [ -z "$(git -C ${TAST_TESTS} status --porcelain)" ]; then
	echo "it seems ${TAST_TESTS} has some uncomitted changes. Please remove them..."
	exit 1
fi
if ! [ -z "$(git -C ${TAST_TESTS} status --ignored --porcelain)" ]; then
	echo "it seems ${TAST_TESTS} has some ignored files. Please remove them (by 'git -C ${TAST_TESTS} clean -f -x -d' or something)."
	exit 1
fi
echo "${TAST_TESTS}: Working directory clean, no ignored files"

CRO3="$(readlink -f "$(git rev-parse --show-toplevel)")"
CRO3_TAST_ANALYZER_DIR="${CRO3}/scripts/tast-analyzer"
if [ -d "${CRO3_TAST_ANALYZER_DIR}" ] ; then
	rm -rf ${CRO3_TAST_ANALYZER_DIR}
fi
mkdir -p "${CRO3_TAST_ANALYZER_DIR}"
cp -r ${TAST_TESTS}/tools/tast-analyzer/* ${CRO3_TAST_ANALYZER_DIR}
echo "Done!"
