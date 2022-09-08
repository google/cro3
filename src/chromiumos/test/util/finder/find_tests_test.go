// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package finder

import (
	"testing"

	"go.chromium.org/chromiumos/config/go/test/api"
)

var testMetadata = []*api.TestCaseMetadata{
	{
		TestCase: &api.TestCase{
			Id: &api.TestCase_Id{
				Value: "id1",
			},
			Name: "test001",
			Tags: []*api.TestCase_Tag{
				{Value: "attr1"},
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
				Value: "id2",
			},
			Name: "test002",
			Tags: []*api.TestCase_Tag{
				{Value: "attr1"},
				{Value: "attr2"},
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
				{Email: "someone1@chromium.org"},
				{Email: "someone2@chromium.org"},
			},
		},
	},
	{
		TestCase: &api.TestCase{
			Id: &api.TestCase_Id{
				Value: "id3",
			},
			Name: "test003",
			Tags: []*api.TestCase_Tag{
				{Value: "attr3"},
				{Value: "attr4"},
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
}

// TestMatchedTestsForSuites makes sure MatchedTestsForSuites return all expected metadata.
func TestMatchedTestsForSuites(t *testing.T) {
	suites := []*api.TestSuite{
		{
			Name: "suite1",
			Spec: &api.TestSuite_TestCaseIds{
				TestCaseIds: &api.TestCaseIdList{
					TestCaseIds: []*api.TestCase_Id{
						{Value: "id1"},
					},
				},
			},
		},
		{
			Name: "suite2",
			Spec: &api.TestSuite_TestCaseTagCriteria_{
				TestCaseTagCriteria: &api.TestSuite_TestCaseTagCriteria{
					Tags:        []string{"attr3"},
					TagExcludes: []string{"attr4"},
				},
			},
		},
	}
	expectedTests := map[string]bool{
		"test001": false,
		"test002": false,
	}
	matchedMdList, err := MatchedTestsForSuites(testMetadata, suites)
	if err != nil {
		t.Fatal("Failed to call MatchedTestsTestsForSuites: ", err)
	}

	for _, md := range matchedMdList {
		found, ok := expectedTests[md.TestCase.Name]
		if !ok {
			t.Errorf("Unexpected metadata: %+v", md)
		}
		if found {
			t.Errorf("Duplicate metadata: %+v", md)
		}
		expectedTests[md.TestCase.Name] = true
	}

	for test, found := range expectedTests {
		if !found {
			t.Errorf("Failed to find test: %v", test)
		}
	}
}

// TestMatchedTestsForSuitesMissing make sure MatchedTestsForSuite return
// error when there is missing metadata..
func TestMatchedTestsForSuitesMissing(t *testing.T) {
	suites := []*api.TestSuite{
		{
			Name: "suite1",
			Spec: &api.TestSuite_TestCaseIds{
				TestCaseIds: &api.TestCaseIdList{
					TestCaseIds: []*api.TestCase_Id{
						{Value: "NotExist"},
					},
				},
			},
		},
	}
	if _, err := MatchedTestsForSuites(testMetadata, suites); err == nil {
		t.Fatal("Failed to get error while calling  MatchedTestsTestsForSuites with non-existing test case")
	}
}

// TestMatch makes sure match return all metadata that match test case tag criteria.
func TestMatch(t *testing.T) {
	md := &api.TestCaseMetadata{
		TestCase: &api.TestCase{
			Id: &api.TestCase_Id{
				Value: "id1",
			},
			Name: "test001",
			Tags: []*api.TestCase_Tag{
				{Value: "attr1"},
				{Value: "attr2"},
			},
		},
	}
	tm := newTagMatcher(&api.TestSuite_TestCaseTagCriteria{
		Tags:        []string{"attr1"},
		TagExcludes: []string{"attr4"},
	})
	if !tm.match(md) {
		t.Fatal("tagMatcher failed to match a matching test metadata")
	}
}

// TestMatchExclude makes sure match exclude metadata that match test case exclude criteria.
func TestMatchExclude(t *testing.T) {
	md := &api.TestCaseMetadata{
		TestCase: &api.TestCase{
			Id: &api.TestCase_Id{
				Value: "id1",
			},
			Name: "test001",
			Tags: []*api.TestCase_Tag{
				{Value: "attr1"},
				{Value: "attr4"},
			},
		},
	}
	tm := newTagMatcher(&api.TestSuite_TestCaseTagCriteria{
		Tags:        []string{"attr1"},
		TagExcludes: []string{"attr4"},
	})
	if tm.match(md) {
		t.Fatal("tagMatcher failed to exclude a test metadata")
	}
}
