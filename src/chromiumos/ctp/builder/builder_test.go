// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package builder

import (
	"testing"
)

func TestTmp(t *testing.T) {
	tmp := tmp()

	if tmp != true {
		t.Errorf("Unexpected diff, %t, %t", tmp, true)
	}
}
