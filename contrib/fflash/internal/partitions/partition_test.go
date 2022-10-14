// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package partitions

import (
	"testing"

	"github.com/frankban/quicktest"
)

func TestParse(t *testing.T) {
	for name, test := range map[string]struct {
		path      string
		device    string
		delimiter string
		num       int
	}{
		"sata": {
			path:      "/dev/sda3",
			device:    "/dev/sda",
			delimiter: "",
			num:       3,
		},
		"emmc": {
			path:      "/dev/mmcblk0p3",
			device:    "/dev/mmcblk0",
			delimiter: "p",
			num:       3,
		},
		"nvme": {
			path:      "/dev/nvme0n1p5",
			device:    "/dev/nvme0n1",
			delimiter: "p",
			num:       5,
		},
	} {
		t.Run(name, func(t *testing.T) {
			qt := quicktest.New(t)

			device, delimiter, number, err := parse(test.path)
			qt.Assert(err, quicktest.IsNil)
			qt.Check(device, quicktest.Equals, test.device)
			qt.Check(delimiter, quicktest.Equals, test.delimiter)
			qt.Check(number, quicktest.Equals, test.num)
		})
	}
}
