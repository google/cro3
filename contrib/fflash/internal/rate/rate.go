// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package rate

import "time"

type record struct {
	value float64
	time  time.Time
}

type Estimator struct {
	ring *ring[record]
}

func NewEstimator(count int) *Estimator {
	return &Estimator{
		ring: newRing[record](count),
	}
}

// AddRecord adds a timestamped value to the estimator.
// The average added value per second is returned.
func (e *Estimator) AddRecord(value float64) float64 {
	back := record{
		value: value,
		time:  time.Now(),
	}
	e.ring.Push(back)
	front := e.ring.Front()
	t := back.time.Sub(front.time).Seconds()
	if t == 0 {
		return 0
	}
	return (back.value - front.value) / t
}
