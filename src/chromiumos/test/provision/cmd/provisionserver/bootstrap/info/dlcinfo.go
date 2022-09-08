// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// DLC constants and helpers
package info

const (
	DlcCacheDir    = "/var/cache/dlc"
	DlcImage       = "dlc.img"
	DlcLibDir      = "/var/lib/dlcservice/dlc"
	DlcPackage     = "package"
	DlcVerified    = "verified"
	DlcserviceUtil = "dlcservice_util"
)

const (
	dlcSlotA string = "dlc_a"
	dlcSlotB string = "dlc_b"
)

var ActiveDlcMap = map[string]string{PartitionNumRootA: dlcSlotA, PartitionNumRootB: dlcSlotA}
var InactiveDlcMap = map[string]string{PartitionNumRootA: dlcSlotB, PartitionNumRootB: dlcSlotB}
