// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
// Package errors defines and implements the error with status used by testexecservice.

package errors

// Status defines different exit code for testexecservice.
type Status int

// StatusError stores both the exit status and the actual error.
type StatusError struct {
	status Status
	err    error
}

// Error return the actual error
func (e *StatusError) Error() error {
	return e.err
}

// Status returns the status code.
func (e *StatusError) Status() Status {
	return e.status
}

// NewStatusError creates a StatusError with the passed status code and formatted string.
func NewStatusError(status Status, err error) *StatusError {
	if status == Success {
		return &StatusError{status: status, err: nil}
	}
	return &StatusError{status: status, err: err}
}

// Following constants are possible value for the status of StatusError.
const (
	Success Status = iota // NoError indicates there is no errors.

	// Exit code 30 - 59 will be reserved for user related errors
	MarshalError                = iota + 30 // Failed to marshal data.
	UnmarshalError                          // Failed to unmarshal data.
	InvalidArgument = iota + 35             // Invalid argument.
	MissingArgument                         // Missing argument.

	// Exit code 60 - 100 will be reserved for server related errors.
	IOCreateError        = iota + 60 // Failed to create file or directory.
	IOAccessError                    // Failed to access file or directory.
	ConnectionError      = iota + 70 // Failed to connect.
	ServerStartingError  = iota + 80 // Failed to start a GRPC server.
	MessageSendingError  = iota + 85 // Failed to send message.
	CommandStartingError = iota + 90 // Failed to start a command.
	CommandExitError                 // Command exit with error.
)
