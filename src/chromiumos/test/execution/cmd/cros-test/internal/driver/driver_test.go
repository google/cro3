// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package driver

import (
	"fmt"
	"testing"

	"chromiumos/test/execution/errors"

	"go.chromium.org/chromiumos/config/go/test/api"
)

var mdList = &api.TestCaseMetadataList{
	Values: []*api.TestCaseMetadata{
		{
			TestCase: &api.TestCase{
				Id: &api.TestCase_Id{
					Value: "some_unique_id",
				},
				Name: "test_case_tast",
				Tags: []*api.TestCase_Tag{
					{Value: "1"},
					{Value: "attr2"},
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
					{Email: "someone2@chromium.org"},
				},
			},
		},
		{
			TestCase: &api.TestCase{
				Id: &api.TestCase_Id{
					Value: "another_unique_id",
				},
				Name: "test_case_tauto",
				Tags: []*api.TestCase_Tag{
					{Value: "attr1"},
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
					{Email: "someone1@chromium.org"},
					{Email: "someone2@chromium.org"},
				},
			},
		},
		{
			TestCase: &api.TestCase{
				Id: &api.TestCase_Id{
					Value: "again_unique_id",
				},
				Name: "test_case_gtest",
				Tags: []*api.TestCase_Tag{
					{Value: "attr1"},
					{Value: "attr2"},
					{Value: "attr3"},
				},
			},
			TestCaseExec: &api.TestCaseExec{
				TestHarness: &api.TestHarness{
					TestHarnessType: &api.TestHarness_Gtest_{
						Gtest: &api.TestHarness_Gtest{},
					},
				},
			},
			TestCaseInfo: &api.TestCaseInfo{
				Owners: []*api.Contact{
					{Email: "someone1@chromium.org"},
				},
			},
		},
	},
}

func GetTestCaseByName(name string) (*api.TestCase, error) {
	for _, tc := range mdList.Values {
		if tc.TestCase.Name == name {
			return tc.TestCase, nil
		}
	}

	return nil, errors.NewStatusError(errors.CommandExitError, fmt.Errorf("Could not find TestCase data for test cast name '%s'", name))
}

// TestDriverToTestsMapping make sure driverToTestsMapping return correct values.
func TestNamesToIds(t *testing.T) {
	testNamesToIds := getTestNamesToIds(mdList.Values)

	if len(testNamesToIds) != len(mdList.Values) {
		t.Fatalf("Got unexpected number of tests from getTestNamesToIds %d: want %d",
			len(testNamesToIds), len(mdList.Values))
	}

	// Loop through and check values
	for name, id := range testNamesToIds {
		if tc, err := GetTestCaseByName(name); err == nil {
			if tc.Name != name {
				t.Errorf("Expected name '%s' does not match actual name '%s'", tc.Name, name)
			}
			if tc.Id.Value != id {
				t.Errorf("Expected id '%s' does not match actual id '%s'", tc.Id.Value, id)
			}
		} else {
			t.Errorf(err.Error())
		}
	}
}

func TestNames(t *testing.T) {
	testNames := getTestNames(mdList.Values)

	if len(testNames) != len(mdList.Values) {
		t.Fatalf("Got unexpected number of tests from testNames %d: want %d",
			len(testNames), len(mdList.Values))
	}

	for _, name := range testNames {
		if _, err := GetTestCaseByName(name); err != nil {
			t.Error(err.Error())
		}
	}
}
