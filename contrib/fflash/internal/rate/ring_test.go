// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package rate

import (
	"testing"
)

func assertFrontBack[T comparable](t *testing.T, r *ring[T], front, back T) {
	t.Helper()

	if r.Front() != front {
		t.Errorf("r.Front() = %v; want %v", r.Front(), front)
	}
	if r.Back() != back {
		t.Errorf("r.Back() = %v; want %v", r.Back(), back)
	}
}

func assertEmpty[T comparable](t *testing.T, r *ring[T], empty bool) {
	t.Helper()

	if r.Empty() != empty {
		t.Errorf("r.Empty() = %v; want %v", r.Empty(), empty)
	}
}

func TestRing(t *testing.T) {
	r := newRing[int](4)
	assertEmpty(t, r, true)

	r.Push(1)
	assertFrontBack(t, r, 1, 1)
	assertEmpty(t, r, false)

	r.Push(2)
	assertFrontBack(t, r, 1, 2)
	assertEmpty(t, r, false)

	r.Push(3)
	assertFrontBack(t, r, 1, 3)
	assertEmpty(t, r, false)

	r.Push(4)
	assertFrontBack(t, r, 1, 4)
	assertEmpty(t, r, false)

	r.Push(5)
	assertFrontBack(t, r, 2, 5)
	assertEmpty(t, r, false)

	r.Push(6)
	assertFrontBack(t, r, 3, 6)
	assertEmpty(t, r, false)

	r.Push(7)
	assertFrontBack(t, r, 4, 7)
	assertEmpty(t, r, false)

	r.Push(8)
	assertFrontBack(t, r, 5, 8)
	assertEmpty(t, r, false)

	r.Push(9)
	assertFrontBack(t, r, 6, 9)
	assertEmpty(t, r, false)
}

func TestEmptyRingBackPanic(t *testing.T) {
	empty := newRing[int](1)

	defer func() {
		if r := recover(); r == nil {
			t.Errorf("Did not panic with empty.Back()")
		}
	}()

	empty.Back()
}

func TestEmptyRingFrontPanic(t *testing.T) {
	empty := newRing[int](1)

	defer func() {
		if r := recover(); r == nil {
			t.Errorf("Did not panic with empty.Front()")
		}
	}()

	empty.Front()
}
