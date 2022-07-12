// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Plain Old Go Object for root disk information
package metadata

import common_utils "chromiumos/test/provision/v2/common-utils"

// RootInfo stores Root information pertaining to a DUT
type RootInfo struct {
	Root          string
	RootDisk      string
	RootPartNum   string
	PartitionInfo *common_utils.PartitionInfo
}
