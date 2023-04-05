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
	cmd, err := cli.ParseInputs()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to parse inputs: %s\n", err)
		cli.NewCLICommand().Usage()
		cli.NewServerCommand().Usage()
		os.Exit(2)
	}
	if err = cmd.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "Android Provision failed: %v\n", err)
		os.Exit(1)
	}
}
