// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package lro

import (
	"context"
	"math/rand"
	"time"

	"go.chromium.org/chromiumos/config/go/api/test/tls/dependencies/longrunning"
	"go.chromium.org/luci/common/clock"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	status "google.golang.org/grpc/status"
)

// Wait waits until the long-running operation specified by the provided
// operation name is done. If the operation is already done,
// it returns immediately.
// Unlike OperationsClient's WaitOperation(), it only returns on context
// timeout or completion of the operation.
func Wait(ctx context.Context, client longrunning.OperationsClient, name string, opts ...grpc.CallOption) (*longrunning.Operation, error) {
	// Exponential backoff is used for retryable gRPC errors. In future, we
	// may want to make these parameters configurable.
	const initialBackoffMillis = 1000
	const maxAttempts = 4
	attempt := 0

	// WaitOperation() can return before the provided timeout even though the
	// underlying operation is in progress. It may also fail for retryable
	// reasons. Thus, we must loop until timeout ourselves.
	for {
		// WaitOperation respects timeout in the RPC Context as well as through
		// an explicit field in WaitOperationRequest. We depend on Context
		// cancellation for timeouts (like everywhere else in this codebase).
		// On timeout, WaitOperation() will return an appropriate error
		// response.
		op, err := client.WaitOperation(ctx, &longrunning.WaitOperationRequest{
			Name: name,
		}, opts...)
		switch status.Code(err) {
		case codes.OK:
			attempt = 0
		case codes.Unavailable, codes.ResourceExhausted:
			// Retryable error; retry with exponential backoff.
			if attempt >= maxAttempts {
				return op, err
			}
			delay := rand.Int63n(initialBackoffMillis * (1 << attempt))
			clock.Sleep(ctx, time.Duration(delay)*time.Millisecond)
			attempt++
		default:
			// Non-retryable error
			return op, err
		}
		if op.Done {
			return op, nil
		}
	}
}
