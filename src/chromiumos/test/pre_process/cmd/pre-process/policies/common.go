// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package policies

import "fmt"

// SignalFormat is the common format all policies/interface must return for the main filter service to use.
type SignalFormat struct {
	Runs     int
	Failruns int
	Passrate float64
	Signal   bool
}

// Convert the milestone + num into a useful regex for query.
func mileStoneRegex(numMileStones int, mileStone int) string {
	baseStr := fmt.Sprintf("%d", mileStone)
	for i := 1; i <= numMileStones; i++ {
		baseStr = fmt.Sprintf("%s|%s", baseStr, fmt.Sprintf("%d", mileStone-i))
	}
	return baseStr
}
