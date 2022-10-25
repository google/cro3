// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package log contains logging utilities for cros_openwrt_image_builder.
package log

import (
	"log"
	"os"
	"strings"
)

var Logger = NewLogger("")

func NewLogger(prefix string) *log.Logger {
	return log.New(os.Stdout, prefix, log.Lmicroseconds|log.Lmsgprefix)
}

type Writer struct {
	Logger *log.Logger
}

func NewWriter(logger *log.Logger) *Writer {
	return &Writer{
		Logger: logger,
	}
}

func (w *Writer) Write(p []byte) (n int, err error) {
	msg := strings.TrimSuffix(string(p), "\n")
	w.Logger.Println(msg)
	return len(p), nil
}
