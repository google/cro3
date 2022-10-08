// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Service interfaces bases for state-machine construction
package common_utils

import (
	"context"
	"log"
)

// CommandInterface executes a specific step in a state. Note commands are
//
//	intended to interact with a ServiceInterface and as such will have
//	side-effects.
type CommandInterface interface {
	//Execute runs the command
	Execute(log *log.Logger) error

	// Revert reverts the command
	Revert() error

	// GetErrorMessage returns a crafted error message in case of failure
	GetErrorMessage() string
}

// ServiceState is a single state representation.
type ServiceState interface {
	// Execute Runs the state
	Execute(ctx context.Context, log *log.Logger) error
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

	// CleanupOnFailure "undoes" the service execution to the extent possible,
	// removing temporary files, and, if feasible, reverting the run commands.
	// CleanupOnFailure function will be called if any ServiceState returns an
	// error when running Execute().
	// |states| will include all ServiceStates that were run; naturally, all of
	// them but last one would have succeeded to Execute().
	// |executionErr| is the error returned by Execute() of the last (failed)
	// ServiceState.
	CleanupOnFailure(states []ServiceState, executionErr error) error
}
