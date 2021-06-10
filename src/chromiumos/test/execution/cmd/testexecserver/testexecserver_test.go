// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"

	"github.com/golang/protobuf/jsonpb"
	"github.com/google/go-cmp/cmp"
	_go "go.chromium.org/chromiumos/config/go"
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

	m := jsonpb.Marshaler{}
	encodedData, err := m.MarshalToString(expReq)
	if err != nil {
		t.Fatal("Failed to marshall request")
	}
	td, err := ioutil.TempDir("", "testexecserver_TestReadInput_*")
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

func TestWriteOutput(t *testing.T) {
	resultDir := "/tmp/tast/results"
	tests := []string{
		"PassedTest",
		"FailedTest",
		"SkippedTest",
	}
	expectedRspn := api.RunTestsResponse{
		TestCaseResults: []*api.TestCaseResult{
			{
				TestCaseId: &api.TestCase_Id{Value: tests[0]},
				ResultDirPath: &_go.StoragePath{
					HostType: _go.StoragePath_LOCAL,
					Path:     filepath.Join(resultDir, "tests", tests[0]),
				},
				Verdict: &api.TestCaseResult_Pass_{Pass: &api.TestCaseResult_Pass{}},
			},
			{
				TestCaseId: &api.TestCase_Id{Value: tests[1]},
				ResultDirPath: &_go.StoragePath{
					HostType: _go.StoragePath_LOCAL,
					Path:     filepath.Join(resultDir, "tests", tests[1]),
				},
				Verdict: &api.TestCaseResult_Fail_{Fail: &api.TestCaseResult_Fail{}},
			},
			{
				TestCaseId: &api.TestCase_Id{Value: tests[2]},
				ResultDirPath: &_go.StoragePath{
					HostType: _go.StoragePath_LOCAL,
					Path:     filepath.Join(resultDir, "tests", tests[2]),
				},
				Verdict: &api.TestCaseResult_Error_{Error: &api.TestCaseResult_Error{}},
			},
		},
	}
	td, err := ioutil.TempDir("", "faketestrunner_TestWriteOutput_*")
	if err != nil {
		t.Fatal("Failed to create temporary dictectory: ", err)
	}
	defer os.RemoveAll(td)
	fn := filepath.Join(td, "t.json")
	if err := writeOutput(fn, &expectedRspn); err != nil {
		t.Fatalf("Failed to write file %v: %v", fn, err)
	}
	f, err := os.Open(fn)
	if err != nil {
		t.Fatalf("Failed to read response from file %v: %v", fn, err)
	}
	rspn := api.RunTestsResponse{}
	if err := jsonpb.Unmarshal(f, &rspn); err != nil {
		t.Fatalf("Failed to unmarshall data from file %v: %v", fn, err)
	}
	if diff := cmp.Diff(rspn, expectedRspn, cmp.AllowUnexported(api.RunTestsResponse{})); diff != "" {
		t.Errorf("Got unexpected data from writeOutput (-got +want):\n%s", diff)
	}
}
