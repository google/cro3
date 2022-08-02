// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"testing"

	qt "github.com/frankban/quicktest"
)

func TestBuilderPathRegexp(t *testing.T) {
	c := qt.New(t)

	for input, item := range map[string]struct {
		output BuilderPath
		errMsg string
	}{
		"cherry-release/R99-12345.6.7": {
			BuilderPath{
				"cherry",
				"R99-12345.6.7",
			},
			"",
		},
		"cherry64-release/R99-12345.6.7": {
			BuilderPath{
				"cherry64",
				"R99-12345.6.7",
			},
			"",
		},
		"kukui-arc-r-release/R99-12345.6.7": {
			BuilderPath{
				"kukui-arc-r",
				"R99-12345.6.7",
			},
			"",
		},
		"invalid-release/R99-???": {
			BuilderPath{},
			"cannot parse builder path: invalid-release/R99-???",
		},
		// TODO(aaronyu): I remember seeing this form but the code cannot handle this now.
		"invalid/R99-12345.6.7": {
			BuilderPath{},
			"cannot parse builder path: invalid/R99-12345.6.7",
		},
	} {
		t.Run(input, func(t *testing.T) {
			out, err := parseBuilderPath(input)
			c.Check(out, qt.Equals, item.output)
			if item.errMsg == "" {
				c.Check(err, qt.Equals, nil)
			} else {
				c.Check(err.Error(), qt.Equals, item.errMsg)
			}
		})
	}
}
