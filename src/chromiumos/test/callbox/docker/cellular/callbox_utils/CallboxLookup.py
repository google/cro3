# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Dict that takes DUT host names as the key and returns the callbox
that it is connected to. DUTs need to be added to this as they are
set up.
"""

callboxes = {
        'chromeos1-donutlab-callbox1-host1.cros':
        'chromeos1-donutlab-callbox1.cros',
        'chromeos1-donutlab-callbox1-host1':
        'chromeos1-donutlab-callbox1.cros',
        'chromeos1-donutlab-callbox2-host1.cros':
        'chromeos1-donutlab-callbox2.cros',
        'chromeos1-donutlab-callbox2-host1':
        'chromeos1-donutlab-callbox2.cros',
        'chromeos1-donutlab-callbox3-host1.cros':
        'chromeos1-donutlab-callbox3.cros',
        'chromeos1-donutlab-callbox3-host1':
        'chromeos1-donutlab-callbox3.cros',
        'chromeos1-donutlab-callbox4-host1.cros':
        'chromeos1-donutlab-callbox4.cros',
        'chromeos1-donutlab-callbox4-host1':
        'chromeos1-donutlab-callbox4.cros',
}
