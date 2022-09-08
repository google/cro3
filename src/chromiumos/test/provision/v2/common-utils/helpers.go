// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Common helper methods
package common_utils

import (
	"context"
	"fmt"
	"path"
	"strings"

	"go.chromium.org/chromiumos/config/go/test/api"
)

// BucketJoin is equivalent to Path.Join(), but for gs buckets.
// This is necessary as the BUF removes double-slashes, which mangles the URI.
// Returns the bucket and append as a formed bucket URI.
func BucketJoin(bucket string, append string) string {
	if strings.HasPrefix(bucket, "gs://") {
		bucket = bucket[5:]
	}
	return fmt.Sprintf("gs://%s", path.Join(bucket, append))
}

// ExecuteStateMachine runs a specific state machine
func ExecuteStateMachine(ctx context.Context, cs ServiceState) (api.InstallResponse_Status, error) {
	for cs != nil {
		if err := cs.Execute(ctx); err != nil {
			return api.InstallResponse_STATUS_PROVISIONING_FAILED, fmt.Errorf("failed provisioning on %s step, %s", cs.Name(), err)
		}
		cs = cs.Next()
	}
	return api.InstallResponse_STATUS_OK, nil
}
