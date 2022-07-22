// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dut

import (
	"context"
	"encoding/gob"
	"fmt"
	"log"
	"os"
	"time"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/logging"
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/progress"
)

func Main() error {
	var r Request
	if err := gob.NewDecoder(os.Stdin).Decode(&r); err != nil {
		return fmt.Errorf("cannot decode flash request: %s", err)
	}
	logging.SetUp(time.Now().Add(-r.ElapsedTimeWhenSent))
	log.SetPrefix("[dut-agent] ")

	ctx := context.Background()

	partState, err := ActivePartitions(ctx)
	if err != nil {
		return fmt.Errorf("cannot get active partitions: %s", err)
	}
	log.Printf("active kernel/rootfs: %s, %s", partState.ActiveKernel(), partState.ActiveRootfs())
	log.Printf("flashing to: %s, %s", partState.InactiveKernel(), partState.InactiveRootfs())

	pr := progress.NewProgressReporter()
	ch := make(chan error)

	go func(rw *progress.ReportingWriter) {
		ch <- r.Flash(ctx, rw, KernelImage, partState.InactiveKernel())
	}(pr.NewWriter("kernel"))
	go func(rw *progress.ReportingWriter) {
		ch <- r.Flash(ctx, rw, RootfsImage, partState.InactiveRootfs())
	}(pr.NewWriter("rootfs"))
	go func(rw *progress.ReportingWriter) {
		ch <- r.FlashStateful(ctx, rw)
	}(pr.NewWriter("stateful"))

	var failed []error
	completed := 0
	ticker := time.NewTicker(time.Second)
	for completed < 3 {
		select {
		case err := <-ch:
			if err != nil {
				failed = append(failed, err)
				log.Println(err)
			}
			completed += 1
		case <-ticker.C:
			log.Println("flash", pr.Report())
		}
	}
	ticker.Stop()
	if len(failed) > 0 {
		return fmt.Errorf("flash failed: %s", err)
	}
	log.Println("flash", pr.Report())

	log.Println("running postinst")
	if err := RunPostinst(ctx, partState.InactiveRootfs()); err != nil {
		return fmt.Errorf("postinst failed: %s", err)
	}

	log.Println("disabling rootfs verification")
	if err := DisableRootfsVerification(ctx, partState.InactiveKernelNum); err != nil {
		return fmt.Errorf("disable rootfs verification failed: %s", err)
	}

	log.Println("clearing tpm owner")
	if err := ClearTpmOwner(ctx); err != nil {
		return fmt.Errorf("clear tpm owner failed: %s", err)
	}

	return nil
}
