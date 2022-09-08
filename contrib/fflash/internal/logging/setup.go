// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package logging

import (
	"fmt"
	"io"
	"log"
	"os"
	"time"
)

type timingLogWriter struct {
	t0 time.Time
}

var _ io.Writer = timingLogWriter{}

func (w timingLogWriter) Write(b []byte) (int, error) {
	return fmt.Fprintf(os.Stderr, "%6.2fs %s", time.Since(w.t0).Seconds(), string(b))
}

func SetUp(t0 time.Time) {
	log.SetFlags(0)
	log.SetOutput(timingLogWriter{t0})
}
