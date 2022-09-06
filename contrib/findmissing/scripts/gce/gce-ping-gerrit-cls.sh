#!/bin/bash
#
# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


WORKSPACE="${HOME}/findmissing_workspace"
GERRIT="${WORKSPACE}/chromite/bin/gerrit"
FINDMISSING="${WORKSPACE}/dev-util/contrib/findmissing"
cd "${FINDMISSING}" || exit
LOG_FILE="/var/log/findmissing/findmissing.log"
# unit: day(s)
THRESHOLD=7
ROTATED_REVIEWERS="tzungbi@chromium.org"

to_string() {
    delta="$1"

    days=$((delta / 86400))
    hours=$(((delta - days * 86400) / 3600))

    echo "${days} day(s) ${hours} hours"
}

get_chromium_reviewers() {
    cl_num="$1"

    # Filter out commit-bot@chromium.org
    "${GERRIT}" --json inspect "${cl_num}" |
        jq -c -r '.[].currentPatchSet.approvals | .[] | select(.type == "CRVW") | .by.email |
                    select(contains("chromium.org"))' |
        grep -v "commit-bot"
}

{
    echo "Triggered ping Gerrit CLs at $(date)"

    now=$(date +%s)
    threshold=$((86400 * THRESHOLD))

    "${GERRIT}" --json mine |
        jq -c -r '.[] | {cl_num:.number, last_updated:.lastUpdated, change_id:.id, branch:.branch}' |
        while read -r record; do
            cl_num=$(echo "${record}" | jq -r .cl_num)
            last_updated=$(echo "${record}" | jq -r .last_updated)
            change_id=$(echo "${record}" | jq -r .change_id)
            branch=$(echo "${record}" | jq -r .branch | cut -d- -f2)

            echo "Checking CL ${cl_num}"

            diff=$((now - last_updated))
            if [[ ${diff} -le ${threshold} ]]; then
                echo "..Age: $(to_string "${diff}")"
                continue
            fi

            echo "..Hasn't been changed for more than ${THRESHOLD} day(s)"

            if [[ -z "$(get_chromium_reviewers "${cl_num}")" ]]; then
                "${GERRIT}" reviewers "${cl_num}" "${ROTATED_REVIEWERS}"
            fi

            "${GERRIT}" message "${cl_num}" \
                "The CL hasn't been changed for more than ${THRESHOLD} day(s)"

            reasons=$(./env/bin/python gerrit_interface.py "${change_id}" "${branch}" |
                        jq -c -r '.attention_set | flatten | .[].reason' 2>/dev/null)
            if echo "${reasons}" | grep -q "Run succeeded"; then
                echo "..CQ+1 has passed"
                continue
            fi

            echo "..Mark CQ+1"
            "${GERRIT}" label-cq "${cl_num}" 1
        done

    echo "End of ping Gerrit CLs at $(date)"
} >> "${LOG_FILE}" 2>&1
