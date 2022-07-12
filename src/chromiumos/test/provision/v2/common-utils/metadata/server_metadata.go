// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Plain Old Go Object for persisting Server information
package metadata

import (
	"log"

	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
)

// ServerMetadata stores server specific information for a DUT
type ServerMetadata struct {
	Port       int
	Log        *log.Logger
	Dut        *lab_api.Dut
	DutAddress string
}
