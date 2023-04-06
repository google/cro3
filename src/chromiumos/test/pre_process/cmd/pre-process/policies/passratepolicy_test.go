// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package policies

import (
	"testing"
)

func TestDetermineSignalFromQuery(t *testing.T) {
	qi := PassRatePolicy{requiredPassRate: 99.0}
	qi.forceMapEnable = listToMap([]string{"Test1"})
	qi.forceMapDisable = listToMap([]string{"Test2"})

	if !qi.determineSignalFromQuery("Test1", 98.0) {
		t.Fatalf("ForceEnableCheck - Test marked as unstable when should be marked as stable.")
	}
	if qi.determineSignalFromQuery("Test2", 99.5) {
		t.Fatalf("ForceDisableCheck - Test marked as stable when should be marked as unstable.")
	}
	if qi.determineSignalFromQuery("Test3", 98.0) {
		t.Fatalf("PassRateCheckUnstable - Test marked as stable when should be marked as unstable.")
	}
	if !qi.determineSignalFromQuery("Test4", 99.0) {
		t.Fatalf("PassRateCheckStable - Test marked as unstable when should be marked as stable.")
	}

}

func TestPopulateMissingTests(t *testing.T) {
	qi := PassRatePolicy{
		data:          make(map[string]SignalFormat),
		otherData:     make(map[string]SignalFormat),
		missingTcList: listToMap([]string{"missing1", "missing2"})}

	sigData := SignalFormat{Signal: true}

	qi.otherData["missing2"] = sigData
	qi.populateMissingTests()
	data, ok := qi.data["missing2"]
	if !ok {
		t.Fatalf("MissingDataCheck - data from missing not backfiled into primary data")
	}
	if data != sigData {
		t.Fatalf("MissingDataCheck - backfiled missing data incorret")

	}

	_, ok = qi.data["missing"]
	if ok {
		t.Fatalf("MissingDataCheck - Missing data got backfilled (how??)")
	}
}
