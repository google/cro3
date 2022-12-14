// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package driver implements drivers to execute tests.
package common

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"go.chromium.org/chromiumos/config/go/test/api"
)

const NO_STATUS = "----"
const START = "START"

// Example: START	----	tast.health.ProbeInputInfo	timestamp=1670924318	localtime=Dec 13 09:38:38
// The first %s is to optionally add a tab.
const baseStr = "%s%s\t%s\t%s\ttimestamp=%d\tlocaltime=%s\t%s\n"

// PublishTkoStatusFile publishes the responseProto into a TKO status log in the given resultsDirectory.
func PublishTkoStatusFile(resultsDir string, results []*api.TestCaseResult) error {
	// NOTE: this entire file can be pulled out of cros-test and places somewhere else in the stack if needed, as long as the resultsProto is provided.

	// Used in the event a test is skipped and/or reported without a time, as TKO needs one.
	defaultInt := time.Now().Unix()
	content, err := generateTkoLog(results, defaultInt)
	if err != nil {
		return err
	}

	if err := writeInfoToStatusLog(content, resultsDir); err != nil {
		return err
	}

	return nil
}

func generateTkoLog(results []*api.TestCaseResult, defaultInt int64) ([]string, error) {
	// Default int will be used when there is no start time.
	var content []string
	for _, result := range results {
		name := result.GetTestCaseId().GetValue()
		verdict := result.Verdict
		reason := result.GetReason()

		startInt := defaultInt
		rTime := result.GetStartTime()
		if rTime != nil {
			startInt = result.GetStartTime().Seconds
		}

		duration := int64(0)
		dur := result.GetDuration()
		if dur != nil {
			duration = result.GetDuration().Seconds
		}

		finishTime := startInt + duration

		tm := time.Unix(startInt, 0)
		startStr := tm.UTC().Format("Dec _2 15:04:05")
		finsihTm := time.Unix(finishTime, 0)
		finishStr := finsihTm.UTC().Format("Dec _2 15:04:05")

		// Translate the verdict type to a tko string.
		var verdictStr string
		switch verdict.(type) {
		case *api.TestCaseResult_Crash_:
			verdictStr = "FAIL"
		case *api.TestCaseResult_Fail_:
			verdictStr = "FAIL"
		case *api.TestCaseResult_Abort_:
			verdictStr = "FAIL"
		case *api.TestCaseResult_Pass_:
			verdictStr = "PASS"
		case *api.TestCaseResult_Skip_:
			verdictStr = "SKIP"
		case *api.TestCaseResult_NotRun_:
			verdictStr = "NOT_RUN"
		}

		content = writeStartLine(content, name, startInt, startStr)
		content = writeInfoLine(content, verdictStr, name, finishTime, finishStr, reason)
		content = writeEndLine(content, verdictStr, name, finishTime, finishStr, reason)

	}

	return content, nil
}

func writeInfoToStatusLog(content []string, resultsDir string) error {
	fn := filepath.Join(resultsDir, "status.log")

	wf, err := os.Create(fn)
	if err != nil {
		return err
	}
	defer wf.Close()
	for _, line := range content {
		wf.WriteString(line)
	}
	return nil
}

func writeStartLine(content []string, name string, timestamp int64, localtime string) []string {
	return append(content, fmt.Sprintf(baseStr, "", START, NO_STATUS, name, timestamp, localtime, ""))
}

func writeInfoLine(content []string, result string, name string, timestamp int64, localtime string, info string) []string {
	return append(content, fmt.Sprintf(baseStr, "\t", result, NO_STATUS, name, timestamp, localtime, info))
}

func writeEndLine(content []string, result string, name string, timestamp int64, localtime string, info string) []string {
	return append(content, fmt.Sprintf(baseStr, "", fmt.Sprintf("END %s", result), NO_STATUS, name, timestamp, localtime, ""))
}
