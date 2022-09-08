// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/protobuf/proto"
)

func TestReadInput(t *testing.T) {
	expReq := &api.CrosTestFinderRequest{
		TestSuites: []*api.TestSuite{
			{
				Name: "suite1",
				Spec: &api.TestSuite_TestCaseIds{
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
			{
				Name: "suite2",
				Spec: &api.TestSuite_TestCaseTagCriteria_{
					TestCaseTagCriteria: &api.TestSuite_TestCaseTagCriteria{
						Tags: []string{"group:meta"},
					},
				},
			},
		},
	}

	m := jsonpb.Marshaler{}
	encodedData, err := m.MarshalToString(expReq)
	if err != nil {
		t.Fatal("Failed to marshall request")
	}
	td, err := ioutil.TempDir("", "cros-test-finder_TestReadInput_*")
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

	if !proto.Equal(req, expReq) {
		t.Errorf("Got unexpected request from readInput (-got +want):\n%v\n--\n%v\n", req, expReq)
	}
}

func TestWriteOutput(t *testing.T) {
	testInfos := []*api.TestCase{}
	for _, md := range []string{"example.Pass", "example.Fail"} {
		testInfos = append(testInfos, &api.TestCase{
			Id: &api.TestCase_Id{Value: md},
		})
	}
	expectedRspn := api.CrosTestFinderResponse{
		TestSuites: []*api.TestSuite{
			{
				Name: "suite1",
				Spec: &api.TestSuite_TestCases{
					TestCases: &api.TestCaseList{TestCases: testInfos},
				},
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
	rspn := api.CrosTestFinderResponse{}
	if err := jsonpb.Unmarshal(f, &rspn); err != nil {
		t.Fatalf("Failed to unmarshall data from file %v: %v", fn, err)
	}

	if !proto.Equal(&rspn, &expectedRspn) {
		t.Errorf("Got unexpected reports(-got +want):\n%v\n--\n%v\n", &rspn, &expectedRspn)
	}
}

func TestCombineSuiteNames(t *testing.T) {
	suites := []*api.TestSuite{
		{
			Name: "suite1",
			Spec: &api.TestSuite_TestCaseIds{
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
		{
			Name: "suite2",
			Spec: &api.TestSuite_TestCaseTagCriteria_{
				TestCaseTagCriteria: &api.TestSuite_TestCaseTagCriteria{
					Tags: []string{"group:meta"},
				},
			},
		},
	}
	name := combineTestSuiteNames(suites)
	if name != "suite1,suite2" {
		t.Errorf(`Got %s from combineTestSuiteNames; wanted "suite1,suite2"`, name)
	}
}

func TestMetadataToTestSuite(t *testing.T) {
	mdList := []*api.TestCaseMetadata{
		{
			TestCase: &api.TestCase{
				Id: &api.TestCase_Id{
					Value: "tast/test001",
				},
				Name: "tastTest",
				Tags: []*api.TestCase_Tag{
					{Value: "attr1"},
					{Value: "attr2"},
				},
				Dependencies: []*api.TestCase_Dependency{
					{Value: "dep1"},
					{Value: "dep2"},
				},
			},
			TestCaseExec: &api.TestCaseExec{
				TestHarness: &api.TestHarness{
					TestHarnessType: &api.TestHarness_Tast_{
						Tast: &api.TestHarness_Tast{},
					},
				},
			},
			TestCaseInfo: &api.TestCaseInfo{
				Owners: []*api.Contact{
					{Email: "someone1@chromium.org"},
				},
			},
		},
		{
			TestCase: &api.TestCase{
				Id: &api.TestCase_Id{
					Value: "tauto/test002",
				},
				Name: "tautoTest",
				Tags: []*api.TestCase_Tag{
					{Value: "attr1"},
					{Value: "attr2"},
				},
			},
			TestCaseExec: &api.TestCaseExec{
				TestHarness: &api.TestHarness{
					TestHarnessType: &api.TestHarness_Tauto_{
						Tauto: &api.TestHarness_Tauto{},
					},
				},
			},
			TestCaseInfo: &api.TestCaseInfo{
				Owners: []*api.Contact{
					{Email: "someone2@chromium.org"},
				},
			},
		},
		{
			TestCase: &api.TestCase{
				Id: &api.TestCase_Id{
					Value: "tauto/test003",
				},
				Name: "tautoTest",
				Tags: []*api.TestCase_Tag{
					{Value: "attr3"},
				},
			},
			TestCaseExec: &api.TestCaseExec{
				TestHarness: &api.TestHarness{
					TestHarnessType: &api.TestHarness_Tauto_{
						Tauto: &api.TestHarness_Tauto{},
					},
				},
			},
			TestCaseInfo: &api.TestCaseInfo{
				Owners: []*api.Contact{
					{Email: "someone3@chromium.org"},
				},
			},
		},
	}
	testInfos := []*api.TestCase{}
	testNames := []string{"tast/test001", "tauto/test002", "tauto/test003"}
	testDeps := [][]string{{"dep1", "dep2"}, {}, {}}
	for i := range testNames {
		deps := []*api.TestCase_Dependency{}
		for _, dep := range testDeps[i] {

			deps = append(deps, &api.TestCase_Dependency{Value: dep})
		}
		if len(deps) == 0 {
			deps = nil
		}
		testInfos = append(testInfos, &api.TestCase{
			Id:           &api.TestCase_Id{Value: testNames[i]},
			Dependencies: deps,
		})

	}
	expected := api.TestSuite{
		Name: "test_suite",
		Spec: &api.TestSuite_TestCases{
			TestCases: &api.TestCaseList{TestCases: testInfos},
		},
	}
	suites := metadataToTestSuite("test_suite", mdList)

	if !proto.Equal(suites, &expected) {
		t.Errorf("Got unexpected test suite from metadataToTestSuite (-got +want):\n%v\n--\n%v\n", suites, &expected)
	}
}
