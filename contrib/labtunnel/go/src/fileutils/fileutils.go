// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package fileutils defines generic file utilities.
package fileutils

import (
	"context"
	"io"
)

// ContextualReaderWrapper is a wrapper around an existing io.Reader that allows
// for the interruption of reads with the cancellation of a context.
type ContextualReaderWrapper struct {
	ctx    context.Context
	reader io.Reader
}

// NewContextualReaderWrapper initializes a new ContextualReaderWrapper.
func NewContextualReaderWrapper(ctx context.Context, reader io.Reader) *ContextualReaderWrapper {
	return &ContextualReaderWrapper{
		ctx:    ctx,
		reader: reader,
	}
}

// Read calls io.Reader.Read on the wrapped reader, allowing for interruption
// from a cancellation of the context.
func (c *ContextualReaderWrapper) Read(p []byte) (n int, err error) {
	readChan := make(chan error)
	go func() {
		readChan <- func() error {
			n, err = c.reader.Read(p)
			return err
		}()
	}()
	select {
	case <-c.ctx.Done():
		err = c.ctx.Err()
		break
	case err = <-readChan:
		break
	}
	return n, err
}
