// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package policies

import (
	"chromiumos/test/pre_process/cmd/pre-process/interfaces"
	"log"
)

// StabilityFromStabilitySenosr wiill get Stability info from the StabilitySensor endpoint.
func StabilityFromStabilitySensor() map[string]SignalFormat {
	data := interfaces.CallForStability()
	return formatStabilityData(data)
}

func formatStabilityData(raw []interfaces.SensorFormat) map[string]SignalFormat {
	log.Println("STABILITY INTERFACE NOT IMPLEMENTED.")
	data := make(map[string]SignalFormat)
	for _, item := range raw {

		status := false
		if item.Test_stats.Stats == "STABLE" {
			status = true
		}
		data[item.Test_id] = SignalFormat{Signal: status}
	}
	return data
}
