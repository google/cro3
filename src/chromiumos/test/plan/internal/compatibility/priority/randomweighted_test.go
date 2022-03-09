// Copyright 2022 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package priority_test

import (
	"math"
	"math/rand"
	"testing"

	"chromiumos/test/plan/internal/compatibility/priority"

	"github.com/google/go-cmp/cmp"
	"go.chromium.org/chromiumos/infra/proto/go/testplans"
)

func TestRandomWeighted_MixedPriorities(t *testing.T) {
	boardPriorityList := &testplans.BoardPriorityList{
		BoardPriorities: []*testplans.BoardPriority{
			{
				SkylabBoard: "boardA",
				Priority:    -100,
			},
			{
				SkylabBoard: "boardB",
				Priority:    -99,
			},
			{
				SkylabBoard: "boardC",
				Priority:    -50,
			},
			{
				SkylabBoard: "boardD",
				Priority:    100,
			},
		},
	}

	selector := priority.NewRandomWeightedSelector(
		rand.New(rand.NewSource(7)), boardPriorityList,
	)

	counts := make(map[string]int)
	for i := 0; i < 1000; i++ {
		selected, err := selector.Select("DUT_POOL_QUOTA", []string{"boardA", "boardB", "boardC", "boardD", "undefinedBoard"})
		if err != nil {
			t.Fatal(err)
		}
		counts[selected] += 1
	}

	// The probabilities are computed from configured priorities as follows:
	// 1. Flip signs: 100, 99, 50, -100.
	// 2. Shift so minimum is 1 (and add default probability for the undefined
	//    board): 201, 200, 151, 1, 101
	// 3. Divide by the sum (654): 0.3073, 0.3058, 0.2309, 0.0015, 0.1544
	expected := map[string]int{
		"boardA":         322,
		"boardB":         303,
		"boardC":         221,
		"boardD":         5,
		"undefinedBoard": 149,
	}
	if diff := cmp.Diff(expected, counts); diff != "" {
		t.Errorf("Unexpected counts of chosen boards (-want +got): %s", diff)
	}
}

func TestRandomWeighted_AllPositivePriorities(t *testing.T) {
	boardPriorityList := &testplans.BoardPriorityList{
		BoardPriorities: []*testplans.BoardPriority{
			{
				SkylabBoard: "boardA",
				Priority:    100,
			},
			{
				SkylabBoard: "boardB",
				Priority:    50,
			},
			{
				SkylabBoard: "boardC",
				Priority:    10,
			},
		},
	}

	selector := priority.NewRandomWeightedSelector(
		rand.New(rand.NewSource(7)), boardPriorityList,
	)

	counts := make(map[string]int)
	for i := 0; i < 1000; i++ {
		selected, err := selector.Select("DUT_POOL_QUOTA", []string{"boardA", "boardB", "boardC", "undefinedBoard"})
		if err != nil {
			t.Fatal(err)
		}
		counts[selected] += 1
	}

	// The probabilities are computed from configured priorities as follows:
	// 1. Flip signs: -100, -50, -10
	// 2. Shift so minimum is 1 (and add default probability for the undefined
	//    board): 1, 51, 91, 101
	// 3. Divide by the sum (244): 0.0041, 0.2090, 0.3730, 0.4139
	expected := map[string]int{
		"boardA":         9,
		"boardB":         202,
		"boardC":         377,
		"undefinedBoard": 412,
	}
	if diff := cmp.Diff(expected, counts); diff != "" {
		t.Errorf("Unexpected counts of chosen boards (-want +got): %s", diff)
	}
}

func TestRandomWeighted_AllNegativePriorities(t *testing.T) {
	boardPriorityList := &testplans.BoardPriorityList{
		BoardPriorities: []*testplans.BoardPriority{
			{
				SkylabBoard: "boardA",
				Priority:    -100,
			},
			{
				SkylabBoard: "boardB",
				Priority:    -50,
			},
			{
				SkylabBoard: "boardC",
				Priority:    -10,
			},
		},
	}

	selector := priority.NewRandomWeightedSelector(
		rand.New(rand.NewSource(7)), boardPriorityList,
	)

	counts := make(map[string]int)
	for i := 0; i < 1000; i++ {
		selected, err := selector.Select("DUT_POOL_QUOTA", []string{"boardA", "boardB", "boardC", "undefinedBoard"})
		if err != nil {
			t.Fatal(err)
		}
		counts[selected] += 1
	}

	// The probabilities are computed from configured priorities as follows:
	// 1. Flip signs: 100, 50, 10
	// 2. Shift so minimum is 1 (and add default probability for the undefined
	//    board): 101, 51, 11, 1
	// 3. Divide by the sum (164): 0.6159, 0.3110, 0.0671, 0.0061
	expected := map[string]int{
		"boardA":         629,
		"boardB":         292,
		"boardC":         68,
		"undefinedBoard": 11,
	}
	if diff := cmp.Diff(expected, counts); diff != "" {
		t.Errorf("Unexpected counts of chosen boards (-want +got): %s", diff)
	}
}

func TestRandomWeighted_SingleBoard(t *testing.T) {
	boardPriorityList := &testplans.BoardPriorityList{
		BoardPriorities: []*testplans.BoardPriority{
			{
				SkylabBoard: "boardA",
				Priority:    -100,
			},
			{
				SkylabBoard: "boardB",
				Priority:    -50,
			},
			{
				SkylabBoard: "boardC",
				Priority:    -10,
			},
		},
	}

	selector := priority.NewRandomWeightedSelector(
		rand.New(rand.NewSource(7)), boardPriorityList,
	)

	selected, err := selector.Select("DUT_POOL_QUOTA", []string{"boardA"})
	if err != nil {
		t.Fatal(err)
	}

	if selected != "boardA" {
		t.Errorf("expected \"boardA\" to be selected, got %q", selected)
	}
}

func TestRandomWeighted_NoBoards(t *testing.T) {
	boardPriorityList := &testplans.BoardPriorityList{
		BoardPriorities: []*testplans.BoardPriority{
			{
				SkylabBoard: "boardA",
				Priority:    -100,
			},
			{
				SkylabBoard: "boardB",
				Priority:    -50,
			},
			{
				SkylabBoard: "boardC",
				Priority:    -10,
			},
		},
	}

	selector := priority.NewRandomWeightedSelector(
		rand.New(rand.NewSource(7)), boardPriorityList,
	)

	_, err := selector.Select("DUT_POOL_QUOTA", []string{})
	if err == nil {
		t.Error("expected error from calling Select with no boards.")
	}
}

func TestRandomWeighted_LargePriorities(t *testing.T) {
	boardPriorityList := &testplans.BoardPriorityList{
		BoardPriorities: []*testplans.BoardPriority{
			{
				SkylabBoard: "boardA",
				Priority:    -int32(math.Pow(2, 30)),
			},
			{
				SkylabBoard: "boardB",
				Priority:    -int32(math.Pow(2, 29)),
			},
			{
				SkylabBoard: "boardC",
				Priority:    int32(math.Pow(2, 21)),
			},
		},
	}

	selector := priority.NewRandomWeightedSelector(
		rand.New(rand.NewSource(7)), boardPriorityList,
	)

	counts := make(map[string]int)
	for i := 0; i < 1000; i++ {
		selected, err := selector.Select("DUT_POOL_QUOTA", []string{"boardA", "boardB", "boardC", "undefinedBoard"})
		if err != nil {
			t.Fatal(err)
		}
		counts[selected] += 1
	}

	// boardA should be chosen approximately twice as much as boardB. boardC
	// should be chosen approximately 1 / 512 choices.
	expected := map[string]int{
		"boardA":         679,
		"boardB":         318,
		"undefinedBoard": 3,
	}
	if diff := cmp.Diff(expected, counts); diff != "" {
		t.Errorf("Unexpected counts of chosen boards (-want +got): %s", diff)
	}
}

func TestRandomWeighted_UnconfiguredPool(t *testing.T) {
	boardPriorityList := &testplans.BoardPriorityList{
		BoardPriorities: []*testplans.BoardPriority{
			{
				SkylabBoard: "boardA",
				Priority:    -500,
			},
			{
				SkylabBoard: "boardB",
				Priority:    -100,
			},
			{
				SkylabBoard: "boardC",
				Priority:    1000,
			},
		},
	}

	selector := priority.NewRandomWeightedSelector(
		rand.New(rand.NewSource(7)), boardPriorityList,
	)

	counts := make(map[string]int)
	for i := 0; i < 1000; i++ {
		selected, err := selector.Select("unconfiguredpool", []string{"boardA", "boardB", "boardC", "undefinedBoard"})
		if err != nil {
			t.Fatal(err)
		}
		counts[selected] += 1
	}

	// Since there is no configuration for the pool, every board gets default
	// priority, and should be chosen equally.
	expected := map[string]int{
		"boardA":         247,
		"boardB":         258,
		"boardC":         239,
		"undefinedBoard": 256,
	}
	if diff := cmp.Diff(expected, counts); diff != "" {
		t.Errorf("Unexpected counts of chosen boards (-want +got): %s", diff)
	}
}
