// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package priority

import (
	"errors"
	"fmt"
	"math/rand"
	"sort"

	"github.com/golang/glog"
	"go.chromium.org/chromiumos/infra/proto/go/testplans"
)

// RandomWeightedSelector selects from a list of boards, with a random choice
// weighted by BoardPriorities. The algorithm is as follows:
//
// 1. The sign of priorities is flipped, so that the board with the most
//    negative configured priority now has the most positive priority.
// 2. If a priority is not defined for a board, it is implicitly 0, as defined
//    in the BoardPriority proto comment.
// 3. Priorities are shifted so that the minimum priority is 1.
// 4. Priorities are divided by the sum of the shifted priorities. At this
//    point, the priorities form a probability distribution (each is in the
//    range (0, 1], and they sum to 1). Each board's probability is proportional
//    to its original configured priority, i.e. the board with the most negative
//    configured priority has the highest probability.
// 5. Sample a board from the probability distribution.
type RandomWeightedSelector struct {
	rand            *rand.Rand
	boardToPriority map[string]*testplans.BoardPriority
}

// NewRandomWeightedSelector returns a RandomWeightedSelector based on
// boardPriorityList.
func NewRandomWeightedSelector(rand *rand.Rand, boardPriorityList *testplans.BoardPriorityList) *RandomWeightedSelector {
	boardToPriority := make(map[string]*testplans.BoardPriority)
	for _, boardPriority := range boardPriorityList.GetBoardPriorities() {
		boardToPriority[boardPriority.GetSkylabBoard()] = boardPriority
	}

	return &RandomWeightedSelector{rand: rand, boardToPriority: boardToPriority}
}

// floatPriority is similar to the BoardPriority proto, but supports float
// priorities for internal computations.
type floatPriority struct {
	board    string
	priority float64
}

// getPriority looks up the configured priority for a given (board, pool)
// combination. The bool return value indicates whether a configured priority
// was found for the combination (similar to a map's return values).
//
// Currently only DUT_POOL_QUOTA has priorities configured.
// TODO(b/224916762): Modify this to look up by pool once the configuration is
// available.
func (rw *RandomWeightedSelector) getPriority(board, pool string) (*testplans.BoardPriority, bool) {
	if pool != "DUT_POOL_QUOTA" {
		glog.Warningf("no priority data configured for pool %q", pool)
		return nil, false
	}

	pri, found := rw.boardToPriority[board]
	return pri, found
}

// RandomWeightedSelector makes assertions that computed values fall within
// expected ranges, e.g. probabilities are <= 1.0. Add some tolerance to avoid
// panics due to possible small floating point imprecisions.
const floatErrorTolerance = 0.001

// Select randomly chooses a board from boards, with the probability a board is
// chosen proportional to its configured probability.
func (rw *RandomWeightedSelector) Select(pool string, boards []string) (string, error) {
	if len(boards) == 0 {
		return "", errors.New("boards must be non-empty")
	}

	var normalizedPriorities []floatPriority
	// For each board in boards, look up its priority and store a floatPriority
	// with the sign flipped from the configured priority. If a board is not
	// found in the configured priorities, it gets priority 0.
	for _, board := range boards {
		if priority, found := rw.getPriority(board, pool); found {
			normalizedPriorities = append(normalizedPriorities, floatPriority{
				board: board, priority: float64(-priority.GetPriority()),
			})
		} else {
			normalizedPriorities = append(normalizedPriorities, floatPriority{
				board: board, priority: 0,
			})
		}
	}

	sort.SliceStable(normalizedPriorities, func(i, j int) bool {
		return normalizedPriorities[i].priority < normalizedPriorities[j].priority
	})

	// Shift the priorities so the minimum is 1, and compute the sum of the
	// shifted priorities.
	minPriority := normalizedPriorities[0].priority
	sumPriorities := 0.0
	for i := range normalizedPriorities {
		normalizedPriorities[i].priority -= (minPriority - 1)
		sumPriorities += normalizedPriorities[i].priority
	}

	// Divide each priority by the sum, each priority must be in the range
	// (0, 1] after.
	for i := range normalizedPriorities {
		normalizedPriorities[i].priority /= sumPriorities

		if normalizedPriorities[i].priority <= 0-floatErrorTolerance || normalizedPriorities[i].priority > 1+floatErrorTolerance {
			panic(fmt.Sprintf("normalized priorities must be in range (0, 1], got %f", normalizedPriorities[i].priority))
		}
	}

	// randFloat is in the range [0.0, 1.0). Compute the cumulative probabilites
	// and find the first value for which randFloat < cdf(priority).
	randFloat := rw.rand.Float64()
	cumulativePriority := 0.0
	for _, priority := range normalizedPriorities {
		cumulativePriority += priority.priority

		if cumulativePriority > 1+floatErrorTolerance {
			panic(fmt.Sprintf("cumulative priority must be <= 1, got %f", cumulativePriority))
		}

		if randFloat < cumulativePriority {
			return priority.board, nil
		}
	}

	panic(fmt.Sprintf("rand.Float64() is > cumulativePriority (%f > %f)", randFloat, cumulativePriority))
}
