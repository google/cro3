// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Houses metadata format retrieved from LaCrOS image
package lacros_metadata

type LaCrOSMetadata struct {
	Content struct {
		Version string `json:"version"`
	} `json:"content"`
}
