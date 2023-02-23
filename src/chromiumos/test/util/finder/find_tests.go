// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package finder find all matched tests from test metadata based on test criteria.
package finder

import (
	"fmt"
	"path/filepath"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type tagMatcher struct {
	tags             map[string]struct{}
	excludes         map[string]struct{}
	testNames        map[string]struct{}
	testNameExcludes map[string]struct{}
}

func newTagMatcher(criteria *api.TestSuite_TestCaseTagCriteria) *tagMatcher {
	tags := make(map[string]struct{})
	for _, tag := range criteria.Tags {
		tags[tag] = struct{}{}
	}
	excludes := make(map[string]struct{})
	for _, tag := range criteria.TagExcludes {
		excludes[tag] = struct{}{}
	}
	testNames := make(map[string]struct{})
	for _, testName := range criteria.TestNames {
		testNames[testName] = struct{}{}
	}
	testNameExcludes := make(map[string]struct{})
	for _, testNameExclude := range criteria.TestNameExcludes {
		testNameExcludes[testNameExclude] = struct{}{}
	}
	return &tagMatcher{
		tags:             tags,
		excludes:         excludes,
		testNames:        testNames,
		testNameExcludes: testNameExcludes,
	}
}

func (tm *tagMatcher) match(md *api.TestCaseMetadata) bool {
	if len(md.TestCase.Tags) < len(tm.tags) {
		return false
	}
	// If the test id is in ANY excluded names, do not match it
	for testNameExclude := range tm.testNameExcludes {
		if matched, _ := filepath.Match(testNameExclude, md.TestCase.Id.Value); matched {
			return false
		}
	}
	// If the test tag is in ANY of the excludes, do not match
	// If the tag is in ANY of the includes (and not excludes), match it
	matchedTags := make(map[string]struct{})
	for _, tag := range md.TestCase.Tags {
		if _, ok := tm.excludes[tag.Value]; ok {
			return false
		}
		if _, ok := tm.tags[tag.Value]; ok {
			matchedTags[tag.Value] = struct{}{}
		}
	}
	// If the ANY names are provided, and the test matches ANY name, include it
	matchTestNames := len(tm.testNames) == 0
	for testName := range tm.testNames {
		if matched, _ := filepath.Match(testName, md.TestCase.Id.Value); matched {
			matchTestNames = true
			break
		}
	}
	return len(matchedTags) == len(tm.tags) && matchTestNames
}

// MatchedTestsForSuites finds all test metadata that match the specified suites.
func MatchedTestsForSuites(metadataList []*api.TestCaseMetadata, suites []*api.TestSuite) (tmList []*api.TestCaseMetadata, err error) {
	tests := make(map[string]struct{})
	var tagMatchers []*tagMatcher
	for _, s := range suites {
		tcIds := s.GetTestCaseIds()
		if tcIds != nil {
			for _, t := range tcIds.TestCaseIds {
				tests[t.Value] = struct{}{}
			}
		}
		criteria := s.GetTestCaseTagCriteria()
		if criteria != nil {
			// create one tag matcher for each test suite that has tags
			tagMatchers = append(tagMatchers, newTagMatcher(criteria))
		}
	}
	defer func() {
		// Get all the metadata for matched tests.
		for _, tm := range metadataList {
			if _, ok := tests[tm.TestCase.Id.Value]; ok {
				tmList = append(tmList, tm)
				delete(tests, tm.TestCase.Id.Value)
			}
		}
		if len(tests) > 0 {
			// There are unmatched tests cases.
			var unmatched []string
			for t := range tests {
				unmatched = append(unmatched, t)
			}
			err = fmt.Errorf("following test ids have no metadata %v", unmatched)
		}
	}()
	if len(tagMatchers) == 0 {
		return tmList, nil
	}
	for _, tm := range metadataList {
		if _, ok := tests[tm.TestCase.Id.Value]; ok {
			// The test has already been included.
			continue
		}
		for _, matcher := range tagMatchers {
			if matcher.match(tm) {
				tests[tm.TestCase.Id.Value] = struct{}{}
				break
			}
		}
	}

	return tmList, nil
}
