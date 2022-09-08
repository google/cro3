// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
// Package errors defines and implements the error with status used by testexecservice.

package errors

import (
	"io"
)

// Status defines different exit code for testexecservice.
type Status int

// StatusError stores both the exit status and the actual error.
type StatusError struct {
	status Status
	err    error
}

// Unwrap return the actual error
func (e *StatusError) Error() string {
	if e.err == nil {
		return ""
	}
	return e.err.Error()
}

// Unwrap return the actual error
func (e *StatusError) Unwrap() error {
	return e.err
}

// Status returns the status code.
func (e *StatusError) Status() Status {
	return e.status
}

// NewStatusError creates a StatusError with the passed status code and error.
func NewStatusError(status Status, err error) *StatusError {
	if status == Success {
		return &StatusError{status: status, err: nil}
	}
	return &StatusError{status: status, err: err}
}

// WriteError writes a newline-terminated fatal error to w and returns the status code to use when exiting.
// If err is not a *StatusError, status code 1 is returned.
func WriteError(w io.Writer, err error) int {
	if err == nil {
		return int(Success)
	}
	var msg string
	var status int

	if se, ok := err.(*StatusError); ok {
		if se.status == Success || err == nil {
			return int(Success)
		}
		msg = se.err.Error()
		status = int(se.status)
	} else {
		msg = err.Error()
		status = GeneralError
	}

	if len(msg) > 0 && msg[len(msg)-1] != '\n' {
		msg += "\n"
	}
	io.WriteString(w, msg)

	return status
}

// Following constants are possible value for the status of StatusError.
const (
	Success Status = 0 // NoError indicates there is no errors.

	GeneralError = 1 // It is for undefined error, but should be avoid to use if possible.

	// Exit code 30 - 59 will be reserved for user related errors
	MarshalError   = 30 // Failed to marshal data.
	UnmarshalError      // Failed to unmarshal data.

	InvalidArgument = 35 // Invalid argument.
	MissingArgument      // Missing argument.

	// Exit code 60 - 100 will be reserved for server related errors.
	IOCreateError  = 60 // Failed to create file or directory.
	IOAccessError       // Failed to access file or directory.
	IOCaptureError      // Failed to capture stdin/stdout/stderr of command

	ConnectionError = 70 // Failed to connect.

	ServerStartingError = 80 // Failed to start a GRPC server.

	MessageSendingError = 85 // Failed to send message.

	CommandStartingError = 90 // Failed to start a command.
	CommandExitError          // Command exit with error.
)
