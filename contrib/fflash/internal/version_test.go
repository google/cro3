// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"context"
	"testing"

	qt "github.com/frankban/quicktest"
)

func TestGetFlashTargetGS(t *testing.T) {
	c := qt.New(t)

	bucket, dir, err := getFlashTarget(context.Background(), nil, "", &Options{
		GS: "gs://chromeos-image-archive/cherry-release/R104-14911.0.0",
	})

	c.Check(bucket, qt.Equals, "chromeos-image-archive")
	c.Check(dir, qt.Equals, "cherry-release/R104-14911.0.0")
	c.Check(err, qt.Equals, nil)
}
