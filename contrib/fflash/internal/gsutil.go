// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"fmt"

	"cloud.google.com/go/storage"
)

func gsURI(obj *storage.ObjectHandle) string {
	return fmt.Sprintf("gs://%s/%s", obj.BucketName(), obj.ObjectName())
}
