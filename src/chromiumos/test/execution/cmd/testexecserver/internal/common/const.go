// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package common provide command utilies and variables for all components in
// testexecserver to use.
package common

// Constants for different components to use.
const (
	TestExecServerRoot  = "/tmp/test/testexecserver"
	TestRequestJSONFile = "request.json"
	TestResultJSONFile  = "result.json"
	TestResultDir       = "/tmp/test/results"
	TestMetadataDir     = "/tmp/test/metadata"
	AutotestDir         = "/usr/local/autotest/"
)
