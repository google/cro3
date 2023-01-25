// Copyright 2022 The ChromiumOS Authors
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

func TestParseVersion(t *testing.T) {
	c := qt.New(t)

	v, err := parseVersion("R1-2.3.4")
	c.Check(v, qt.Equals, version{r: 1, x: 2, y: 3, z: 4})
	c.Check(err, qt.IsNil, qt.Commentf("%v", err))
}

var versionLessCases = map[string]struct {
	v string
	w string
}{
	// b/266721499
	"b266721499": {"R109-15237.0.0", "R109-15236.80.0"},

	// Compare R###
	"release-num": {"R1-99.99.99", "R2-0.0.0"},

	// Compare branch status
	"branch-status": {"R1-99.0.99", "R1-0.1.0"},

	// Compare Major
	"major":  {"R1-1.0.1", "R1-2.0.0"},
	"major2": {"R1-1.3.1", "R1-2.2.0"},

	// Compare Minor
	"minor1": {"R1-1.1.1", "R1-1.2.0"},
	"minor2": {"R1-1.0.1", "R1-1.2.0"},

	// Compare Patch
	"patch1": {"R1-1.1.0", "R1-1.1.1"},
	"patch2": {"R1-1.1.1", "R1-1.1.2"},
}

func TestVersionLess(t *testing.T) {
	for name, test := range versionLessCases {
		t.Run(
			name,
			func(t *testing.T) {
				pv, err := parseVersion(test.v)
				if err != nil {
					t.Fatal(err)
				}
				pw, err := parseVersion(test.w)
				if err != nil {
					t.Fatal(err)
				}
				if !pv.less(pw) {
					t.Errorf("%q.less(%q) = false; want true", pv, pw)
				}
				if pw.less(pv) {
					t.Errorf("%q.less(%q) = true; want false", pw, pv)
				}
			},
		)
	}
}

func FuzzVersionTotalOrder(f *testing.F) {
	f.Add(1, 2, 3, 4, 1, 2, 3, 4)
	f.Add(1, 2, 3, 4, 1, 2, 3, 5)
	f.Fuzz(func(t *testing.T, vr, vx, vy, vz, wr, wx, wy, wz int) {
		v := version{vr, vx, vy, vz}
		w := version{wr, wx, wy, wz}
		if v == w {
			if v.less(w) {
				t.Errorf("%q < %q", v, w)
			}
			if w.less(v) {
				t.Errorf("%q < %q", w, v)
			}
			return
		}
		if v.less(w) == w.less(v) {
			t.Errorf("v=%q and w=%q not in total order: v<w=%T, w<v=%T", v, w, v.less(w), w.less(v))
		}
	})
}

func FuzzParseVersionRoundTrip(f *testing.F) {
	f.Add(1, 2, 3, 4)
	f.Fuzz(func(t *testing.T, r, x, y, z int) {
		if r < 0 || x < 0 || y < 0 || z < 0 {
			return
		}
		v := version{r, x, y, z}
		w, err := parseVersion(v.String())
		if err != nil {
			t.Fatalf("Cannot parse %q: %v", v, err)
		}
		if v != w {
			t.Errorf("%q != parseVersion(%q) = %q", v, v, w)
		}
	})
}
