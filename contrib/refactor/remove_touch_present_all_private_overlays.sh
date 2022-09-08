#!/bin/bash
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Iterates over all private overlays, finds every model.yaml file that has the
# legacy /touch present cros_config attribute present, deletes the line and then
# generates a CL for each private repo.

cd ../../../../private-overlays
for overlay in *; do
  cd "${overlay}"
  to_refactor=$(grep -r 'present: "' ./ -l | grep model.yaml)
  if [ -n "${to_refactor}" ]; then
    echo "Updating: ${to_refactor}"
    sed -i '/present: "/d' "${to_refactor}"
    overlay_name=$(echo "${overlay}" | cut -d '-' -f2)
    repo start remove-touch-present
    git add -u
    git commit -m"
${overlay_name}: Remove unused touch fields

These probe fields were never used, so removing and instead will provide
probe config that aligns to factory/hwid schema around touch component
probing (which will also be available config if needed somewhere on
platform/build).

BUG=None
TEST=cq
"
    repo upload --ht remove-touch-present
  fi

  cd ..
done
