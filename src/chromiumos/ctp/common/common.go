// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"fmt"
)

// ToKeyvalSlice converts a key-val map to a slice of "key:val" strings.
func ToKeyvalSlice(keyvals map[string]string) []string {
	var s []string
	for key, val := range keyvals {
		s = append(s, fmt.Sprintf("%s:%s", key, val))
	}
	return s
}
