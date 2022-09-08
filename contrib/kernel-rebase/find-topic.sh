#!/bin/bash
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

sha=$1

if [ "${sha}" = "" ]
then
    echo "Need SHA to search topic"
    exit 1
fi

rebasedb=$(python3 -c "from common import rebasedb; print(rebasedb)")

sql="select sha,topic,subject from commits where sha is \"${sha}\""

sqlite3 "${rebasedb}" "${sql}" | sed -e 's/|/\x9/g'
exit 0

tlist=""

while [ "$2" != "" ]
do
    sql="${sql} or topic=$2"
    tlist="${tlist}, $2"
    shift
done

echo "# ${tlist}"

sql="${sql};"

sqlite3 "${rebasedb}" "${sql}" | while read -r line
do
    dotag=0
    fromupstream=0
    conflicts=0

    f1=$(echo "${line}" | awk -F '|' '{print $1}') # disposition
    f2=$(echo "${line}" | awk -F '|' '{print $2}') # sha
    f3=$(echo "${line}" | awk -F '|' '{print $3}') # replacement sha
    f4=$(echo "${line}" | awk -F '|' '{print $4}') # subject

    case "${f1}" in
    "replace")
        f2_old="${f2}"
        f2="${f3}"
        f1="pick"
        fromupstream=1
        ;;
    "pick" | "drop")
        ;;
    "tag")
        # maybe later
        dotag=1
        # f1="pick"
        ;;
    "squash")
        # maybe later
        # f1="pick"
        ;;
    "conflicts")
        # maybe later
        # f1="pick"
        ;;
    *)
        echo "Oops"
        exit 1
        ;;
    esac

    if [ "${f1}" = "squash" ]
    then
        # special processing.
        echo "exec dosquash49.sh ${f2} ${f4}"
        continue
    fi
    if [[ "${f1}" != "pick" && "${f1}" != "edit" && "${f1}" != "reword" ]]
    then
        continue
    fi
    # echo "cherry-picking ${f2}"
    if [ "${fromupstream}" -ne 0 ]
    then
        echo "pick ${f2_old} ${f4}"
        echo "exec fromupstream.py --replace ${f2}"
    elif [ "${dotag}" -ne 0 ]
    then
        echo "pick ${f2} ${f4}"
        echo "exec dotag.sh"
    elif [ "${conflicts}" -ne 0 ]
    then
        echo "exec doconflicts49.sh ${f2} ${f4}"
    else
        echo "${f1} ${f2} ${f4}"
    fi
done
