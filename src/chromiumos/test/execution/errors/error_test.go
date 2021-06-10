// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package errors

import (
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
	{err: errors.New("cfailed to connect to TLW server"), status: ConnectionError},
	{err: errors.New("failed to start TLS service"), status: ServerStartingError},
	{err: errors.New("failed to send request to TLW server"), status: MessageSendingError},
	{err: errors.New("failed to start autotest"), status: CommandStartingError},
	{err: errors.New("tast exits with failure"), status: CommandExitError},
}

// TestError tests the function Error.
func TestError(t *testing.T) {
	for _, es := range errStatuses {
		if es.Error() != es.err {
			t.Errorf("Got unexpected error from Error(%v): got (%v) want (%v))", es, es.Error(), es.err)
		}
	}
}

// TestError tests the function Status.
func TestStatus(t *testing.T) {
	for _, es := range errStatuses {
		if es.Status() != es.status {
			t.Errorf("Got unexpected status from Error(%v): got (%v) want (%v))", es, es.Status(), es.status)
		}
	}
}

// TestError tests the function NewStatusError.
func TestNewStatusError(t *testing.T) {
	for _, es := range errStatuses {
		newEs := NewStatusError(es.status, es.err)
		if newEs.Error() != es.err {
			t.Errorf("Got unexpected error from Error(%v): got (%v) want (%v))", newEs, newEs.Error(), es.err)
		}
		if newEs.Status() != es.status {
			t.Errorf("Got unexpected status from Error(%v): got (%v) want (%v))", newEs, newEs.Status(), es.status)
		}
	}
}
