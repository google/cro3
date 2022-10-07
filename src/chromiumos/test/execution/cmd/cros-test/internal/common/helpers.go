// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package common provide command utilities and variables for all components in
// cros-test to use.
package common

import (
	"bufio"
	"io"
	"log"
)

// TestScanner makes a scanner to read from test streams.
func TestScanner(stream io.Reader, logger *log.Logger, harness string) {
	const maxCapacity = 4096 * 1024
	scanner := bufio.NewScanner(stream)
	// Expand the buffer size to avoid deadlocks on heavy logs
	buf := make([]byte, maxCapacity)
	scanner.Buffer(buf, maxCapacity)
	scanner.Split(bufio.ScanLines)
	for scanner.Scan() {
		logger.Printf("[%v] %v", harness, scanner.Text())
	}
	if scanner.Err() != nil {
		logger.Println("Failed to read pipe: ", scanner.Err())
	}
}
