// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ssh

import (
	_ "embed"
	"os"
)

// SSH RSA private key embedded as bytes.
// https://chromium.googlesource.com/chromiumos/chromite/+/main/ssh_keys/testing_rsa
//
//go:embed testing_rsa
var TestingRSA []byte
var testingRSAFileName = "testing_rsa"

type TestingRSAFile struct {
	filePath string
}

// NewTestingRSAFile generates a new RSA File within a temp dir
func NewTestingRSAFile() (*TestingRSAFile, error) {
	file, err := os.CreateTemp("", "fflash-rsa-*")
	if err != nil {
		return nil, err
	}
	filePath := file.Name()
	file.Close()

	// 400 is minimum permission requirements for the RSA file.
	err = os.WriteFile(filePath, TestingRSA, 0400)
	if err != nil {
		os.Remove(filePath)
		return nil, err
	}

	return &TestingRSAFile{filePath: filePath}, nil
}

// GetFilePath returns file path to the rsa itself
func (f *TestingRSAFile) GetFilePath() string {
	return f.filePath
}

// Delete removes the testing rsa temp file
func (f *TestingRSAFile) Delete() error {
	return os.Remove(f.filePath)
}
