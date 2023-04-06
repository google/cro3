// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"chromiumos/test/pre_process/cmd/pre-process/policies"
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/protobuf/proto"
)

func generateTestCaseResponse(tests []string) *api.CrosTestFinderResponse {
	testInfos := []*api.TestCase{}
	for _, md := range tests {
		testInfos = append(testInfos, &api.TestCase{
			Id: &api.TestCase_Id{Value: md},
		})
	}
	suiteResp := api.CrosTestFinderResponse{
		TestSuites: []*api.TestSuite{
			{
				Name: "suite1",
				Spec: &api.TestSuite_TestCases{
					TestCases: &api.TestCaseList{TestCases: testInfos},
				},
			},
		},
	}
	return &suiteResp
}

func generateMetadataList(tests []string) []*api.TestCaseMetadata {
	testInfos := []*api.TestCaseMetadata{}
	for _, md := range tests {
		tcID := &api.TestCase_Id{Value: md}
		testInfos = append(testInfos, &api.TestCaseMetadata{
			TestCase: &api.TestCase{Id: tcID},
		})
	}
	return testInfos

}

func generateTestMDSuite(tests []string) *api.TestSuite {
	expectedTestInfos := []*api.TestCaseMetadata{}
	for _, md := range tests {
		tcID := &api.TestCase_Id{Value: md}
		expectedTestInfos = append(expectedTestInfos, &api.TestCaseMetadata{
			TestCase: &api.TestCase{Id: tcID},
		})
	}

	suite := &api.TestSuite{
		Name: "suitename",
		Spec: &api.TestSuite_TestCasesMetadata{
			TestCasesMetadata: &api.TestCaseMetadataList{Values: expectedTestInfos},
		},
	}
	return suite
}

func generateTestMDSuites(tests []string) []*api.TestSuite {
	TestSuites := []*api.TestSuite{
		{
			Name: "suite1",
			Spec: &api.TestSuite_TestCasesMetadata{
				TestCasesMetadata: &api.TestCaseMetadataList{Values: generateMetadataList(tests)},
			},
		},
	}
	return TestSuites

}
func generateTestMDesponse(tests []string) *api.CrosTestFinderResponse {
	suiteResp := api.CrosTestFinderResponse{
		TestSuites: generateTestMDSuites(tests),
	}
	return &suiteResp
}

func testCaseRequest() *api.CrosTestFinderResponse {
	return generateTestCaseResponse([]string{"example.Pass", "example.Fail"})

}

func testMDRequest() *api.CrosTestFinderResponse {
	return generateTestMDesponse([]string{"example.Pass", "example.Fail"})

}

func testMdNoFail() *api.CrosTestFinderResponse {
	return generateTestCaseResponse([]string{"example.Pass"})

}

func basicReq(useMD bool) *api.FilterFlakyRequest {
	var TFI *api.CrosTestFinderResponse
	if useMD {
		TFI = testCaseRequest()
	} else {
		TFI = testMDRequest()
	}
	prp := &api.PassRatePolicy{
		PassRate:        99,
		MinRuns:         5,
		NumOfMilestones: 1,
	}
	p := &api.FilterFlakyRequest_PassRatePolicy{
		PassRatePolicy: prp,
	}
	return &api.FilterFlakyRequest{Policy: p, TestFinderInput: TFI, Milestone: "114", DefaultEnabled: true}

}

func TestReadInput(t *testing.T) {
	m := jsonpb.Marshaler{}
	encodedData, err := m.MarshalToString(basicReq(false))
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
	rreq, err := readInput(fn)
	if err != nil {
		t.Fatalf("Failed to read input file %v: %v", fn, err)
	}

	if !proto.Equal(rreq, basicReq(false)) {
		t.Errorf("Got unexpected request from readInput (-got +want):\n%v\n--\n%v\n", rreq, basicReq(false))
	}
}

func TestWriteOutput(t *testing.T) {
	expectedRspn := api.FilterFlakyResponse{
		Response:     testCaseRequest(),
		RemovedTests: []string{},
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
	rspn := api.FilterFlakyResponse{}
	if err := jsonpb.Unmarshal(f, &rspn); err != nil {
		t.Fatalf("Failed to unmarshall data from file %v: %v", fn, err)
	}

	if !proto.Equal(&rspn, &expectedRspn) {
		t.Errorf("Got unexpected reports(-got +want):\n%v\n--\n%v\n", &rspn, &expectedRspn)
	}
}

func TestIsEligible(t *testing.T) {
	tdata := make(map[string]policies.SignalFormat)
	tdata["example.Pass"] = policies.SignalFormat{
		Signal: true,
	}
	tdata["example.Fail"] = policies.SignalFormat{
		Signal: false,
	}

	req := basicReq(false)
	filter := Filter{req: req,
		data: tdata}
	if filter.testEligible("example.Pass") != true {
		t.Fatalf("example.Pass set as not eligable when should be")
	}
	if filter.testEligible("example.Fail") != false {
		t.Fatalf("example.False set as eligable when should not be")
	}

	// Test defaultEnabled flag.
	if filter.testEligible("example.Unknown") != true {
		t.Fatalf("example.Unknown set as not eligable when should be")
	}
	// Test defaultEnabled flag.
	if filter.testEligible("example.Unknown") != true {
		t.Fatalf("example.Unknown set as not eligable when should be")
	}

	// Flip, and test.
	filter.req.DefaultEnabled = false
	// Test defaultEnabled flag.
	if filter.testEligible("example.Unknown") != false {
		t.Fatalf("example.Unknown set as eligable when should not be")
	}

}

func TestFilterCases(t *testing.T) {
	tdata := make(map[string]policies.SignalFormat)
	tdata["example.Pass"] = policies.SignalFormat{
		Signal: true,
	}
	tdata["example.Fail"] = policies.SignalFormat{
		Signal: false,
	}

	req := basicReq(false)
	filter := Filter{req: req,
		data: tdata}

	// Generate a set of tests, these will be used when searching for signal on the tests.
	testInfos := []*api.TestCase{}
	for _, md := range []string{"example.Pass", "example.Fail"} {
		testInfos = append(testInfos, &api.TestCase{
			Id: &api.TestCase_Id{Value: md},
		})
	}

	rspn := filter.filterCases(testInfos, "suitename")

	expectedTestInfos := []*api.TestCase{}
	for _, md := range []string{"example.Pass"} {
		expectedTestInfos = append(expectedTestInfos, &api.TestCase{
			Id: &api.TestCase_Id{Value: md},
		})
	}

	e := &api.TestSuite{
		Name: "suitename",
		Spec: &api.TestSuite_TestCases{
			TestCases: &api.TestCaseList{TestCases: expectedTestInfos},
		},
	}

	if !proto.Equal(rspn, e) {
		t.Errorf("Got unexpected reports:\nGOT:\n%v\nWant:\n%v\n", rspn, e)
	}
}

func TestFilterMetadata(t *testing.T) {
	tdata := make(map[string]policies.SignalFormat)
	tdata["example.Pass"] = policies.SignalFormat{
		Signal: true,
	}
	tdata["example.Fail"] = policies.SignalFormat{
		Signal: false,
	}

	// Req with metadata
	req := basicReq(true)
	filter := Filter{req: req,
		data: tdata}

	// Generate a set of tests, these will be used when searching for signal on the tests.
	foo := &api.TestSuite_TestCasesMetadata{
		TestCasesMetadata: &api.TestCaseMetadataList{Values: generateMetadataList([]string{"example.Pass", "example.Fail"})},
	}
	rspn := filter.filterMetadata(foo, "suitename")

	e := generateTestMDSuite([]string{"example.Pass"})

	if !proto.Equal(rspn, e) {
		t.Errorf("Got unexpected reports:\nGOT:\n%v\nWant:\n%v\n", rspn, e)
	}
}
