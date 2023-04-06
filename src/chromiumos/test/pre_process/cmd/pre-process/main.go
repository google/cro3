// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the pre-process for finding tests based on tags.
package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"time"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/chromiumos/config/go/test/api"

	"chromiumos/test/execution/errors"
	"chromiumos/test/pre_process/cmd/pre-process/policies"
	"chromiumos/test/util/helpers"
)

const (
	defaultRootPath       = "/tmp/test/cros-test-finder"
	defaultInputFileName  = "request.json"
	defaultOutputFileName = "result.json"
)

type Filter struct {
	data     map[string]policies.SignalFormat
	removed  []string
	notFound []string
	req      *api.FilterFlakyRequest
}

func readInput(fileName string) (*api.FilterFlakyRequest, error) {
	f, err := os.Open(fileName)
	if err != nil {
		return nil, errors.NewStatusError(errors.IOAccessError,
			fmt.Errorf("fail to read file %v: %v", fileName, err))
	}
	req := api.FilterFlakyRequest{}
	umrsh := jsonpb.Unmarshaler{}
	umrsh.AllowUnknownFields = true
	if err := umrsh.Unmarshal(f, &req); err != nil {
		return nil, errors.NewStatusError(errors.UnmarshalError,
			fmt.Errorf("fail to unmarshal file %v: %v", fileName, err))
	}

	return &req, nil
}

// writeOutput writes a CrosTestFinderResponse json.
func writeOutput(output string, resp *api.FilterFlakyResponse) error {
	f, err := os.Create(output)
	if err != nil {
		return errors.NewStatusError(errors.IOCreateError,
			fmt.Errorf("fail to create file %v: %v", output, err))
	}
	m := jsonpb.Marshaler{}
	if err := m.Marshal(f, resp); err != nil {
		return errors.NewStatusError(errors.MarshalError,
			fmt.Errorf("failed to marshall response to file %v: %v", output, err))
	}
	return nil
}

// Version is the version info of this command. It is filled in during emerge.
var Version = "<unknown>"
var defaultPort = 8010

type args struct {
	// Common input params.
	logPath   string
	inputPath string
	output    string
	version   bool

	// Server mode params
	port int
}

// filterCases based on the preset f.data. NOTE: f.data must be populated before calling.
func (f *Filter) filterCases(testcases []*api.TestCase, name string) *api.TestSuite {
	keepCases := []*api.TestCase{}
	fmt.Println("Filtering Cases")

	// Iterate through the TC, keep the ones which are given the green.
	for _, tc := range testcases {
		value := tc.Id.Value
		if f.testEligible(value) {
			keepCases = append(keepCases, tc)
		}
	}

	return &api.TestSuite{
		Name: name,
		Spec: &api.TestSuite_TestCases{
			TestCases: &api.TestCaseList{TestCases: keepCases},
		},
	}

}

// filterMetadata based on the preset f.data. NOTE: f.data must be populated before calling.
func (f *Filter) filterMetadata(op *api.TestSuite_TestCasesMetadata, name string) *api.TestSuite {
	keepMetas := []*api.TestCaseMetadata{}
	mdl := op.TestCasesMetadata.Values

	for _, tc := range mdl {
		value := tc.TestCase.Id.Value
		if f.testEligible(value) {
			keepMetas = append(keepMetas, tc)
		}
	}

	return &api.TestSuite{
		Name: name,
		Spec: &api.TestSuite_TestCasesMetadata{
			TestCasesMetadata: &api.TestCaseMetadataList{Values: keepMetas},
		},
	}
}

// testEligible will return false if the stabiliyData shows the test is unstable, else true.
// This indicates that if there is no stabilityData, we will return true.
func (f *Filter) testEligible(value string) bool {
	// This loop doesn't "determine" eligibity, as that is left to the policy.
	// It is simply looping through the given tests, and checking for their "signal" (ie, eligibity)
	// and applying returning that; in conjunction with applying the defaultEnabled rule.
	_, ok := f.data[value]
	isAllowed := false

	// If the test is found in the stabilityData, check for its signal and use that
	if ok {
		isAllowed = f.data[value].Signal == true
		if isAllowed {
			return true
		} else {
			f.removed = append(f.removed, value)
		}
	} else {
		// If the test is not found, and `DefaultEnabled` is set, keep the test
		f.notFound = append(f.notFound, value)
		if f.req.DefaultEnabled {
			return true
		}
	}
	log.Printf("Test %s marked as not eligible.\n", value)
	return false
}

func getStabilityData(req *api.FilterFlakyRequest, tcList map[string]struct{}) (map[string]policies.SignalFormat, error) {
	var data map[string]policies.SignalFormat

	// TODO: this datatype will need to evolve from a board string to something more complex.
	var variant string
	switch variantOp := req.Variant.(type) {
	case *api.FilterFlakyRequest_Board:
		variant = variantOp.Board
	}
	if variant == "" {
		fmt.Println("No variant")
		return nil, fmt.Errorf("no variant provided, cannot filter")
	}

	// Currently 2 types of policies will be supported. This can be expanded if newer types are added.
	switch op := req.Policy.(type) {
	case *api.FilterFlakyRequest_PassRatePolicy:
		data = policies.StabilityFromPolicy(op, variant, req.Milestone, tcList)
	case *api.FilterFlakyRequest_StabilitySensorPolicy:
		data = policies.StabilityFromStabilitySensor()
	}

	return data, nil
}

func testMDToSet(op *api.TestSuite_TestCasesMetadata) map[string]struct{} {
	tcList := make(map[string]struct{})
	mdl := op.TestCasesMetadata.Values
	for _, tc := range mdl {
		value := tc.TestCase.Id.Value
		tcList[value] = struct{}{}
	}

	return tcList
}

func testCasesToSet(testcases []*api.TestCase) map[string]struct{} {
	tcList := make(map[string]struct{})
	for _, tc := range testcases {
		value := tc.Id.Value
		tcList[value] = struct{}{}
	}
	return tcList
}

func innerMain(req *api.FilterFlakyRequest) (*api.FilterFlakyResponse, error) {
	filter := Filter{req: req}
	var filteredSuites []*api.TestSuite
	for _, md := range req.TestFinderInput.TestSuites {
		// The input request, cros-test-finder, can be either TestCases OR TestCaseMetadata. Support both options.
		var filteredSuite *api.TestSuite
		switch op := md.Spec.(type) {
		case *api.TestSuite_TestCases:

			// Generate a set of tests, these will be used when searching for signal on the tests.
			testCases := op.TestCases.TestCases
			// TODO, handle errors
			filter.data, _ = getStabilityData(filter.req, testCasesToSet(testCases))
			filteredSuite = filter.filterCases(testCases, md.Name)
		case *api.TestSuite_TestCasesMetadata:
			// Generate a set of tests, these will be used when searching for signal on the tests.

			// TODO; handle the error.
			filter.data, _ = getStabilityData(filter.req, testMDToSet(op))
			filteredSuite = filter.filterMetadata(op, md.Name)
		}
		filteredSuites = append(filteredSuites, filteredSuite)

	}

	CTFrspn := &api.CrosTestFinderResponse{TestSuites: filteredSuites}

	rspn := &api.FilterFlakyResponse{
		Response:     CTFrspn,
		RemovedTests: filter.removed,
	}

	log.Printf("The following tests are set to be removed from this scheduled attempt:\n %s\n", rspn.RemovedTests)
	return rspn, nil

}

// runCLI is the entry point for running cros-test (TestFinderService) in CLI mode.
func runCLI(ctx context.Context, d []string) int {
	t := time.Now()
	defaultLogPath := filepath.Join(defaultRootPath, t.Format("20060102-150405"))
	defaultRequestFile := filepath.Join(defaultRootPath, defaultInputFileName)
	defaultResultFile := filepath.Join(defaultRootPath, defaultOutputFileName)

	a := args{}

	fs := flag.NewFlagSet("Run pre-process", flag.ExitOnError)
	fs.StringVar(&a.logPath, "log", defaultLogPath, fmt.Sprintf("Path to record finder logs. Default value is %s", defaultLogPath))
	fs.StringVar(&a.inputPath, "input", defaultRequestFile, "specify the test filter request json input file")
	fs.StringVar(&a.output, "output", defaultResultFile, "specify the test filter request json input file")
	fs.BoolVar(&a.version, "version", false, "print version and exit")
	fs.Parse(d)

	if a.version {
		fmt.Println("pre-process version ", Version)
		return 0
	}

	logFile, err := helpers.CreateLogFile(a.logPath)
	if err != nil {
		log.Fatalln("Failed to create log file", err)
		return 2
	}
	defer logFile.Close()
	// logger := helpers.NewLogger(logFile)
	mw := io.MultiWriter(logFile, os.Stderr)
	log.SetOutput(mw)

	log.Println("pre-process version ", Version)

	log.Println("Reading input file: ", a.inputPath)
	req, err := readInput(a.inputPath)
	if err != nil {
		log.Println("Error: ", err)
		return errors.WriteError(os.Stderr, err)
	}

	rspn, err := innerMain(req)
	if err != nil {
		return 2
	}

	log.Println("Writing output file: ", a.output)
	if err := writeOutput(a.output, rspn); err != nil {
		log.Println("Error: ", err)
		return errors.WriteError(os.Stderr, err)
	}

	return 0
}

func mainInternal(ctx context.Context) int {
	return runCLI(ctx, os.Args[1:])
}

func main() {
	os.Exit(mainInternal(context.Background()))
}
