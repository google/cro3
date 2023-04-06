// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package interfaces

import (
	"context"
	"fmt"

	"cloud.google.com/go/bigquery"
)

func QueryForResults(variant string, milestone string) *bigquery.RowIterator {
	ctx := context.Background()
	c, err := bigquery.NewClient(ctx, "chromeos-bot")
	if err != nil {
		fmt.Println("THE PAIN!")
	}

	cmd := fmt.Sprintf("SELECT * FROM chromeos-test-platform-data.analytics.FlakeCache WHERE total_runs > 0 AND board = \"%s\"  AND (REGEXP_CONTAINS(build, \"%s\"))", variant, milestone)
	fmt.Println((cmd))
	bqQ := c.Query(cmd)
	// Execute the query.
	it, err := bqQ.Read(ctx)
	if err != nil {
		fmt.Printf("INFORMATIONAL: query error: %s", err)
	}

	return it
}
