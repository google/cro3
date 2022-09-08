// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package errors

import (
	"bytes"
	"errors"
	"testing"
)

type errorSt struct {
	err     error
	message string
}

var errStatuses = []*StatusError{
	{err: nil, status: Success},
	{err: errors.New("failed to create file"), status: IOCreateError},
	{err: errors.New("failed to read file"), status: IOAccessError},
	{err: errors.New("failed to marshal data"), status: MarshalError},
	{err: errors.New("failed to unmarshal json string"), status: UnmarshalError},
	{err: errors.New("invalid test harness"), status: InvalidArgument},
	{err: errors.New("missing DUT name"), status: MissingArgument},
	{err: errors.New("failed to connect to TLW server"), status: ConnectionError},
	{err: errors.New("failed to start TLS service"), status: ServerStartingError},
	{err: errors.New("failed to send request to TLW server"), status: MessageSendingError},
	{err: errors.New("failed to start autotest"), status: CommandStartingError},
	{err: errors.New("tast exits with failure"), status: CommandExitError},
}

// TestError tests the function Error.
func TestError(t *testing.T) {
	for _, es := range errStatuses {
		msg := es.Error()
		expectedMsg := ""
		if es.Status() != Success {
			expectedMsg = es.err.Error()
		}
		if msg != expectedMsg {
			t.Errorf("Got unexpected error from Error(%v): got (%v) want (%v))", es, msg, expectedMsg)
		}
	}
}

// TestUnwrap tests the function Unwrap.
func TestUnwrap(t *testing.T) {
	for _, es := range errStatuses {
		if es.Unwrap() != es.err {
			t.Errorf("Got unexpected error from Unwrap(%v): got (%v) want (%v))", es, es.Unwrap(), es.err)
		}
	}
}

// TestStatus tests the function Status.
func TestStatus(t *testing.T) {
	for _, es := range errStatuses {
		if es.Status() != es.status {
			t.Errorf("Got unexpected status from Unwrap(%v): got (%v) want (%v))", es, es.Status(), es.status)
		}
	}
}

// TestNewStatusError tests the function NewStatusError.
func TestNewStatusError(t *testing.T) {
	for _, es := range errStatuses {
		newEs := NewStatusError(es.status, es.err)
		if newEs.Unwrap() != es.err {
			t.Errorf("Got unexpected error from Unwrap(%v): got (%v) want (%v))", newEs, newEs.Unwrap(), es.err)
		}
		if newEs.Status() != es.status {
			t.Errorf("Got unexpected status from Status(%v): got (%v) want (%v))", newEs, newEs.Status(), es.status)
		}
	}
}

// TestWriteError tests the function WriterError.
func TestWriteError(t *testing.T) {
	status := IOCreateError
	msg := "failed to create file"
	b := bytes.Buffer{}
	es := NewStatusError(Status(status), errors.New(msg))
	exitCode := WriteError(&b, es)
	if exitCode != status {
		t.Errorf("Got unexpected status from WriteError: got (%v) want (%v))", exitCode, status)
	}
	if b.String() != msg+"\n" {
		t.Errorf("Got unexpected message from WriteError: got (%v) want (%v))", b.String(), msg+"\n")
	}
}

// TestWriteError tests the function WriteError with an error that is not a StatusError.
func TestWriteErrorNotStatusError(t *testing.T) {
	msg := "failed to create file"
	b := bytes.Buffer{}
	err := errors.New(msg)
	exitCode := WriteError(&b, err)
	if exitCode != 1 {
		t.Errorf("Got unexpected status from WriteError: got (%v) want (1))", exitCode)
	}
	if b.String() != msg+"\n" {
		t.Errorf("Got unexpected message from WriteError: got (%v) want (%v))", b.String(), msg+"\n")
	}
}

// TestWriteError tests the function WriteError with no error.
func TestWriteErrorNoError(t *testing.T) {
	status := Success
	msg := ""
	b := bytes.Buffer{}
	es := NewStatusError(Status(status), errors.New(msg))
	exitCode := WriteError(&b, es)
	if exitCode != int(status) {
		t.Errorf("Got unexpected status from WriteError: got (%v) want (%v))", exitCode, status)
	}
	if b.String() != "" {
		t.Errorf(`Got unexpected message from WriteError: got (%q) want (""))`, b.String())
	}
}
