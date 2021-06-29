// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Service interfaces bases
package services

import (
	"context"
)

// ServiceState is a single state representation.
type ServiceState interface {
	// Execute Runs the state
	Execute(ctx context.Context) error
	// Next gets the next state in the state machine
	Next() ServiceState
	// Name gets the fully qualified name of this state
	Name() string
}

// ServiceInterface represents the state machine for this specific service installation.
// It holds installation metadata and provides helpers, including the generator
// of the first state for that installation.
type ServiceInterface interface {
	// GetFirstState returns the first state in this state machine
	GetFirstState() ServiceState
}
