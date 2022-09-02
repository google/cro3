// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Plain Old Go Object for persisting Server information
package metadata

// ServerMetadata stores server specific information for publishing
type ServerMetadata struct {
	Port int
}
