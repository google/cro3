// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package partitions

import (
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

func parse(partition string) (device string, delimiter string, number int, err error) {
	device = strings.TrimRight(partition, "0123456789")
	number, err = strconv.Atoi(partition[len(device):])
	if err != nil {
		return "", "", 0, fmt.Errorf("cannot parse %q as a partition: %v", partition, device)
	}
	if strings.HasSuffix(device, "p") {
		return device[:len(device)-1], "p", number, nil
	} else {
		return device, "", number, nil
	}
}

// State of the device.
type State struct {
	// device path in /dev
	Device string

	// partition delimiter
	Delimiter string

	// partition numbers
	ActiveKernelNum   int
	ActiveRootfsNum   int
	InactiveKernelNum int
	InactiveRootfsNum int
}

func (p *State) partition(num int) string {
	return fmt.Sprintf("%s%s%d", p.Device, p.Delimiter, num)
}

func (p *State) ActiveKernel() string {
	return p.partition(p.ActiveKernelNum)
}

func (p *State) ActiveRootfs() string {
	return p.partition(p.ActiveRootfsNum)
}

func (p *State) InactiveKernel() string {
	return p.partition(p.InactiveKernelNum)
}

func (p *State) InactiveRootfs() string {
	return p.partition(p.InactiveRootfsNum)
}

func GetStateFromRootPartition(rootPart string) (State, error) {
	device, delimiter, activeRootNum, err := parse(rootPart)
	if err != nil {
		return State{}, err
	}

	switch activeRootNum {
	case partNumRootfsA:
		return State{
			Device:            device,
			Delimiter:         delimiter,
			ActiveKernelNum:   partNumKernelA,
			ActiveRootfsNum:   partNumRootfsA,
			InactiveKernelNum: partNumKernelB,
			InactiveRootfsNum: partNumRootfsB,
		}, nil
	case partNumRootfsB:
		return State{
			Device:            device,
			Delimiter:         delimiter,
			ActiveKernelNum:   partNumKernelB,
			ActiveRootfsNum:   partNumRootfsB,
			InactiveKernelNum: partNumKernelA,
			InactiveRootfsNum: partNumRootfsA,
		}, nil
	default:
		return State{}, fmt.Errorf("active root partition %s number %d is invalid", rootPart, activeRootNum)
	}
}
