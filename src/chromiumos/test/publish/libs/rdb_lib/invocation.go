// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package rdb_lib

import (
	"encoding/json"
	"fmt"
	"strings"

	rdb_pb "go.chromium.org/luci/resultdb/proto/v1"
	"google.golang.org/protobuf/encoding/protojson"
)

type Invocation struct {
	invProto         rdb_pb.Invocation
	testResults      []*rdb_pb.TestResult
	testExonerations []*rdb_pb.TestExoneration
}

// Deserialize deserializes data to Invocation data
func Deserialize(data string) (map[string]*Invocation, error) {
	invMap := make(map[string]*Invocation)

	for lineNum, line := range strings.Split(data, "\n") {
		if line == "" {
			continue
		}
		var entry map[string]interface{}
		err := json.Unmarshal([]byte(line), &entry)
		if err != nil {
			return invMap, fmt.Errorf("error while unmarshalling line %d: %s", lineNum+1, err.Error())
		}
		if len(entry) == 0 {
			return invMap, fmt.Errorf("no data found on line %d", lineNum+1)
		}

		invId, ok := entry["invocationId"].(string)
		if !ok {
			return invMap, fmt.Errorf("invocation id not found on line %d", lineNum+1)
		}

		inv, ok := invMap[invId]
		if !ok {
			inv = &Invocation{testResults: []*rdb_pb.TestResult{}, testExonerations: []*rdb_pb.TestExoneration{}}
			invMap[invId] = inv
		}

		// retrieve invocation
		invocationInterface, ok := entry["invocation"]
		if ok {
			data, err := json.Marshal(invocationInterface)
			if err != nil {
				return invMap, fmt.Errorf("error during marshaling invocation at line %d: %s", lineNum+1, err.Error())
			}

			err = protojson.Unmarshal(data, &inv.invProto)
			if err != nil {
				return invMap, fmt.Errorf("error during unmarshalling invocation at line %d: %s", lineNum+1, err.Error())
			}
			continue
		}

		//retrieve test_result
		testResultInterface, ok := entry["testResult"]
		if ok {
			data, err := json.Marshal(testResultInterface)
			if err != nil {
				return invMap, fmt.Errorf("error during marshaling testResult at line %d: %s", lineNum+1, err.Error())
			}

			var testResult rdb_pb.TestResult
			err = protojson.Unmarshal(data, &testResult)
			if err != nil {
				return invMap, fmt.Errorf("error during unmarshalling testResult at line %d: %s", lineNum+1, err.Error())
			}
			inv.testResults = append(inv.testResults, &testResult)
			continue
		}

		//retrieve test_exoneration
		testExonerationInterface, ok := entry["testExoneration"]
		if ok {
			data, err := json.Marshal(testExonerationInterface)
			if err != nil {
				return invMap, fmt.Errorf("error during marshaling testExoneration at line %d: %s", lineNum+1, err.Error())
			}

			var testExoneration rdb_pb.TestExoneration
			err = protojson.Unmarshal(data, &testExoneration)
			if err != nil {
				return invMap, fmt.Errorf("error during unmarshalling testExoneration at line %d: %s", lineNum+1, err.Error())
			}
			inv.testExonerations = append(inv.testExonerations, &testExoneration)
		} else {
			return invMap, fmt.Errorf("no valid key (invocation, testResult, testExoneration) found at line %d", lineNum+1)
		}
	}

	return invMap, nil
}
