// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"log"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/dut"
)

func main() {
	if err := dut.Main(); err != nil {
		log.Fatal(err)
	}
}
