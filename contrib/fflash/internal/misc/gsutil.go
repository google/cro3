// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package misc

import (
	"fmt"
	"path"

	"cloud.google.com/go/storage"
)

// GsURI returns the gs:// URI for the object handle.
func GsURI(obj *storage.ObjectHandle) string {
	return fmt.Sprintf("gs://" + path.Join(obj.BucketName(), obj.ObjectName()))
}
