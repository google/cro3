// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dut

import (
	"context"
	"fmt"
	"strconv"
	"strings"
)

const (
	partNumKernelA = 2
	partNumKernelB = 4
	partNumRootfsA = 3
	partNumRootfsB = 5
	partNumMiniosA = 9
	partNumMiniosB = 10
)

func getActiveRootPartition(ctx context.Context) (string, error) {
	return runCommand(ctx, "rootdev", "-s")
}

func getActiveRootDevice(ctx context.Context) (string, error) {
	return runCommand(ctx, "rootdev", "-s", "-d")
}

func parsePartition(partition string) (device string, number int, err error) {
	device = strings.TrimRight(partition, "0123456789")
	number, err = strconv.Atoi(partition[len(device):])
	if err != nil || !strings.HasSuffix(device, "p") {
		return "", 0, fmt.Errorf("cannot parse %q as a partition: %v", partition, device)
	}
	return device[:len(device)-1], number, nil
}

type PartitionState struct {
	Device            string
	ActiveKernelNum   int
	ActiveRootfsNum   int
	InactiveKernelNum int
	InactiveRootfsNum int
}

func (p *PartitionState) partition(num int) string {
	return fmt.Sprintf("%sp%d", p.Device, num)
}

func (p *PartitionState) ActiveKernel() string {
	return p.partition(p.ActiveKernelNum)
}

func (p *PartitionState) ActiveRootfs() string {
	return p.partition(p.ActiveRootfsNum)
}

func (p *PartitionState) InactiveKernel() string {
	return p.partition(p.InactiveKernelNum)
}

func (p *PartitionState) InactiveRootfs() string {
	return p.partition(p.InactiveRootfsNum)
}

func ActivePartitions(ctx context.Context) (PartitionState, error) {
	rootPart, err := getActiveRootPartition(ctx)
	if err != nil {
		return PartitionState{}, err
	}
	device, activeRootNum, err := parsePartition(rootPart)
	if err != nil {
		return PartitionState{}, err
	}

	switch activeRootNum {
	case partNumRootfsA:
		return PartitionState{
			Device:            device,
			ActiveKernelNum:   partNumKernelA,
			ActiveRootfsNum:   partNumRootfsA,
			InactiveKernelNum: partNumKernelB,
			InactiveRootfsNum: partNumRootfsB,
		}, nil
	case partNumRootfsB:
		return PartitionState{
			Device:            device,
			ActiveKernelNum:   partNumKernelB,
			ActiveRootfsNum:   partNumRootfsB,
			InactiveKernelNum: partNumKernelA,
			InactiveRootfsNum: partNumRootfsA,
		}, nil
	default:
		return PartitionState{}, fmt.Errorf("active root partition %s number %d is invalid", rootPart, activeRootNum)
	}
}
