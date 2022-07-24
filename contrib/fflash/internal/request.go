// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"context"
	"fmt"
	"strings"

	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google/downscope"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/dut"
)

// buildConditionExpression builds the CEL (https://github.com/google/cel-spec)
// expression for restricting Google Cloud Storage access to resources within
// the bucket and with the objectPrefix.
func buildConditionExpression(bucket, objectPrefix string) string {
	name := "projects/_/buckets/" + bucket + "/objects/" + objectPrefix
	if strings.ContainsAny(name, `'"\`) {
		panic("Bad name: " + name)
	}
	return fmt.Sprintf("resource.name.startsWith('%s')", name)
}

// createFlashRequest creates a dut.Request to the dut-agent to perform a flash.
//
// The token is downscoped to only allow access to the Google Cloud Storage directory.
func createFlashRequest(ctx context.Context, token oauth2.TokenSource, bucket, objectPrefix string) (*dut.Request, error) {
	// Downscope with Credential Access Boundaries
	// https://cloud.google.com/iam/docs/downscoping-short-lived-credentials
	down, err := downscope.NewTokenSource(ctx, downscope.DownscopingConfig{
		RootSource: token,
		Rules: []downscope.AccessBoundaryRule{
			{
				AvailableResource: "//storage.googleapis.com/projects/_/buckets/" + bucket,
				AvailablePermissions: []string{
					"inRole:roles/storage.objectViewer",
				},
				Condition: &downscope.AvailabilityCondition{
					Title:       "bound-to-directory",
					Description: "Limit access to the intended directory.",
					Expression:  buildConditionExpression(bucket, objectPrefix),
				},
			},
		},
	})
	if err != nil {
		return nil, fmt.Errorf("downscope.NewTokenSource failed: %w", err)
	}

	tok, err := down.Token()
	if err != nil {
		return nil, fmt.Errorf("down.Token() failed: %w", err)
	}
	tok.RefreshToken = ""

	return &dut.Request{
		Token:     tok,
		Bucket:    bucket,
		Directory: objectPrefix,
	}, nil
}
