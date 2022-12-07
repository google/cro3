// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"testing"

	"github.com/google/go-cmp/cmp"
)

func TestToKeyvalSlice(t *testing.T) {
	m := map[string]string{
		"foo":  "bar",
		"test": "ing",
	}

	want := []string{"foo:bar", "test:ing"}
	got := ToKeyvalSlice(m)

	if diff := cmp.Diff(want, got); diff != "" {
		t.Errorf("unexpected diff (%s)", diff)
	}
}
