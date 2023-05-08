// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"

	"context"
	"errors"
	"log"
	"strings"
	"time"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type WaitForStickyKernel struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewWaitForStickyKernel(ctx context.Context, cs *service.CrOSService) *WaitForStickyKernel {
	return &WaitForStickyKernel{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *WaitForStickyKernel) Execute(log *log.Logger) error {
	log.Printf("Start WaitForStickyKernel Execute")

	pi := common_utils.GetPartitionInfo(c.cs.MachineMetadata.RootInfo.Root,
		c.cs.MachineMetadata.RootInfo.RootDisk,
		c.cs.MachineMetadata.RootInfo.RootPartNum)

	kernalNum := pi.ActiveKernelNum
	// Timeout is determined by 2x delay to mark new kernel successful + 10 seconds fuzz.
	stickyTimeout := 100 * time.Second
	stickyKernelCtx, cancel := context.WithTimeout(c.ctx, stickyTimeout)
	defer cancel()
	twoSeconds := 2 * time.Second

	// Note in CLI mode the context is not built with a timeout, thus we need to check on loop.
	for {
		select {
		case <-stickyKernelCtx.Done():
			return errors.New("kernel never became sticky within timeout")
		default:
			kernelSuccess, err := c.cs.Connection.RunCmd(c.ctx, "cgpt", []string{"show", "-S", "-i", kernalNum, c.cs.MachineMetadata.RootInfo.RootDisk})
			if err != nil {
				log.Printf("WaitForStickyKernel kernel status, %s", err)
			} else if strings.TrimSpace(kernelSuccess) != "1" {
				log.Printf("WaitForStickyKernel kernel not yet sticky")
			} else {
				log.Printf("WaitForStickyKernel kernel is sticky")
				log.Printf("WaitForStickyKernel Success")
				return nil
			}
			time.Sleep(twoSeconds)
		}
	}
}

func (c *WaitForStickyKernel) Revert() error {
	return nil
}

func (c *WaitForStickyKernel) GetErrorMessage() string {
	return "failed to wait for kernel to be sticky"
}

func (c *WaitForStickyKernel) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_STABLIZE_DUT_FAILED
}
