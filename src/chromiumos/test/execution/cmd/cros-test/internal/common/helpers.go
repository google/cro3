// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package common provide command utilities and variables for all components in
// cros-test to use.
package common

import (
	"bufio"
	"fmt"
	"io"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
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

// UnpackMetadata unpacks the Any metadata field into AutotestExecutionMetadata
func UnpackMetadata(req *api.CrosTestRequest) (*api.AutotestExecutionMetadata, error) {
	if req.Metadata == nil {
		return &api.AutotestExecutionMetadata{}, nil
	}

	var m api.AutotestExecutionMetadata
	if err := req.Metadata.UnmarshalTo(&m); err != nil {
		return nil, fmt.Errorf("improperly formatted input proto metadata, %s", err)
	}
	return &m, nil
}
