// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Partition constants and helpers
package info

import (
	"fmt"
	"strings"
)

const (
	LaCrOSRootComponentPath = "/var/lib/imageloader/lacros"
	LaCrOSPageSize          = 4096
)

const (
	PartitionNumKernelA = "2"
	PartitionNumKernelB = "4"
	PartitionNumRootA   = "3"
	PartitionNumRootB   = "5"
)

const (
	StatefulPath           = "/mnt/stateful_partition"
	UpdateStatefulFilePath = StatefulPath + "/.update_available"
)

// partitionsInfo holds active/inactive root + kernel partition information.
type PartitionInfo struct {
	// The active + inactive kernel device partitions (e.g. /dev/nvme0n1p2).
	ActiveKernel   string
	InactiveKernel string
	// The active + inactive root device partitions (e.g. /dev/nvme0n1p3).
	ActiveRoot   string
	InactiveRoot string
}

// GetPartitionInfo retrieves relevant kernel and root info for a specific root
func GetPartitionInfo(root string, rootDisk string, rootPartNum string) PartitionInfo {
	// Determine the next kernel and root.
	rootDiskPartDelim := rootDisk + strings.TrimSuffix(strings.TrimPrefix(root, rootDisk), rootPartNum)
	switch rootPartNum {
	case PartitionNumRootA:
		return PartitionInfo{
			ActiveKernel:   rootDiskPartDelim + PartitionNumKernelA,
			InactiveKernel: rootDiskPartDelim + PartitionNumKernelB,
			ActiveRoot:     rootDiskPartDelim + PartitionNumRootA,
			InactiveRoot:   rootDiskPartDelim + PartitionNumRootB,
		}
	case PartitionNumRootB:
		return PartitionInfo{
			ActiveKernel:   rootDiskPartDelim + PartitionNumKernelB,
			InactiveKernel: rootDiskPartDelim + PartitionNumKernelA,
			ActiveRoot:     rootDiskPartDelim + PartitionNumRootB,
			InactiveRoot:   rootDiskPartDelim + PartitionNumRootA,
		}
	default:
		panic(fmt.Sprintf("Unexpected root partition number of %s", rootPartNum))
	}
}
