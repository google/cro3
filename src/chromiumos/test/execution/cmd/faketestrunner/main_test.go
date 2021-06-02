// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"encoding/json"
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"

	"github.com/google/go-cmp/cmp"
	"go.chromium.org/chromiumos/config/go/test/api"
)

func TestReadInput(t *testing.T) {
	expReq := &api.RunTestsRequest{
		TestSuites: []*api.TestSuite{
			{
				Name: "suite1",
				TestCaseIds: &api.TestCaseIdList{
					TestCaseIds: []*api.TestCase_Id{
						{
							Value: "example.Pass",
						},
						{
							Value: "example.Fail",
						},
					},
				},
			},
		},
		Dut: &api.DeviceInfo{
			PrimaryHost: "127.0.0.1:2222",
		},
	}
	encodedData, _ := json.Marshal(expReq)
	td, err := ioutil.TempDir("", "faketestrunner_TestReadInput_*")
	if err != nil {
		t.Fatal("Failed to create temporary dictectory: ", err)
	}
	defer os.RemoveAll(td)
	fn := filepath.Join(td, "t.json")
	if err := ioutil.WriteFile(fn, []byte(encodedData), 0644); err != nil {
		t.Fatalf("Failed to write file %v: %v", fn, err)
	}
	req, err := readInput(fn)
	if err != nil {
		t.Fatalf("Failed to read input file %v: %v", fn, err)
	}
	if diff := cmp.Diff(req, expReq, cmp.AllowUnexported(api.RunTestsRequest{})); diff != "" {
		t.Errorf("Got unexpected request from readInput (-got +want):\n%s", diff)
	}
}
