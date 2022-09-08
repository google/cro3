// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package rate

import (
	"testing"

	qt "github.com/frankban/quicktest"
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
	c := qt.New(t)
	c.Assert(r.Empty(), qt.Equals, true)

	r.Push(1)
	c.Assert(r.Front(), qt.Equals, 1)
	c.Assert(r.Back(), qt.Equals, 1)
	c.Assert(r.Empty(), qt.Equals, false)

	r.Push(2)
	c.Assert(r.Front(), qt.Equals, 1)
	c.Assert(r.Back(), qt.Equals, 2)
	c.Assert(r.Empty(), qt.Equals, false)

	r.Push(3)
	c.Assert(r.Front(), qt.Equals, 1)
	c.Assert(r.Back(), qt.Equals, 3)
	c.Assert(r.Empty(), qt.Equals, false)

	r.Push(4)
	c.Assert(r.Front(), qt.Equals, 1)
	c.Assert(r.Back(), qt.Equals, 4)
	c.Assert(r.Empty(), qt.Equals, false)

	r.Push(5)
	c.Assert(r.Front(), qt.Equals, 2)
	c.Assert(r.Back(), qt.Equals, 5)
	c.Assert(r.Empty(), qt.Equals, false)

	r.Push(6)
	c.Assert(r.Front(), qt.Equals, 3)
	c.Assert(r.Back(), qt.Equals, 6)
	c.Assert(r.Empty(), qt.Equals, false)

	r.Push(7)
	c.Assert(r.Front(), qt.Equals, 4)
	c.Assert(r.Back(), qt.Equals, 7)
	c.Assert(r.Empty(), qt.Equals, false)

	r.Push(8)
	c.Assert(r.Front(), qt.Equals, 5)
	c.Assert(r.Back(), qt.Equals, 8)
	c.Assert(r.Empty(), qt.Equals, false)

	r.Push(9)
	c.Assert(r.Front(), qt.Equals, 6)
	c.Assert(r.Back(), qt.Equals, 9)
	c.Assert(r.Empty(), qt.Equals, false)
}

func TestEmptyRingPanic(t *testing.T) {
	empty := newRing[int](1)
	qt.Assert(t, func() { empty.Back() }, qt.PanicMatches, ".*")
	qt.Assert(t, func() { empty.Front() }, qt.PanicMatches, ".*")
}
