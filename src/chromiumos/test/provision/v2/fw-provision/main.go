// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"chromiumos/test/provision/v2/fw-provision/cli"
	"fmt"
	"os"
)

func main() {
	opt, err := cli.ParseInputs()
	if err != nil {
		fmt.Printf("unable to parse inputs: %s", err)
		os.Exit(2)
	}
	err = opt.Run()
	if err != nil {
		fmt.Printf("fw-provision failed: %v", err)
		os.Exit(1)
	}
}
