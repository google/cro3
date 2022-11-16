// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"os"

	"chromiumos/test/provision/v2/android-provision/cli"
)

func main() {
	opt, err := cli.ParseInputs()
	if err != nil {
		fmt.Printf("unable to parse inputs: %s\n", err)
		os.Exit(2)
	}
	if err := opt.Run(); err != nil {
		fmt.Printf("Android Provision failed: %v\n", err)
		os.Exit(1)
	}
}
