// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"os"

	"chromiumos/test/local-cft/internal/tasks"
)

func main() {
	os.Exit(tasks.LocalCft())
}
