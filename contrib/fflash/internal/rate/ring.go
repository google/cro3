// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package rate

// ring is a ring buffer with fixed capacity.
type ring[T any] struct {
	data     []T
	head     int
	capacity int
}

func newRing[T any](capacity int) *ring[T] {
	return &ring[T]{
		data:     make([]T, 0, capacity),
		head:     -1,
		capacity: capacity,
	}
}

// Push value to the ring.
// If the ring is full, the oldest object on the ring is removed.
func (r *ring[T]) Push(value T) {
	if len(r.data) < r.capacity {
		r.data = append(r.data, value)
		r.head++
	} else {
		r.head = (r.head + 1) % len(r.data)
		r.data[r.head] = value
	}
}

// Back returns the oldest object on the ring.
// Panics if the ring is empty.
func (r *ring[T]) Back() T {
	return r.data[r.head%len(r.data)]
}

// Front returns the newest object on the ring.
// Panics if the ring is empty.
func (r *ring[T]) Front() T {
	return r.data[(r.head+1)%len(r.data)]
}

// Empty tells if the ring is empty.
func (r *ring[T]) Empty() bool {
	return len(r.data) == 0
}
