// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Plain Old Go Object repo for machine metadata
package metadata

// MachineMetadata stores DUT specific information
type MachineMetadata struct {
	RootInfo RootInfo
	Board    string
}
