// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"context"
	"fmt"
	"io"
	"log"
	"net/url"
	"path"
	"regexp"
	"strconv"
	"strings"

	"cloud.google.com/go/storage"
	"google.golang.org/api/iterator"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/misc"
)

// version like R{r}-{x}.{y}.{z} e.g. R109-15236.80.0
type version struct {
	r int
	x int
	y int
	z int
}

var versionRegexp = regexp.MustCompile(`^R(\d+)-(\d+).(\d+)\.(\d+)$`)

func parseVersion(v string) (version, error) {
	m := versionRegexp.FindStringSubmatch(v)
	if m == nil {
		return version{}, fmt.Errorf("cannot parse %q as version", v)
	}
	var nums [4]int
	for i := range nums {
		var err error
		nums[i], err = strconv.Atoi(m[i+1])
		if err != nil {
			return version{}, fmt.Errorf("cannot parse %q as version: %v", v, err)
		}
	}
	return version{nums[0], nums[1], nums[2], nums[3]}, nil
}

func (v version) branched() bool {
	return v.y != 0
}

func (v version) less(w version) bool {
	if v.r != w.r {
		return v.r < w.r
	}

	// For the same release R###, prefer branched versions.
	// For example R109-15236.80.0 should be preferred to R109-15237.0.0.
	// See also b/259389997.
	if v.branched() != w.branched() {
		return w.branched()
	}

	if v.x != w.x {
		return v.x < w.x
	}
	if v.y != w.y {
		return v.y < w.y
	}
	return v.z < w.z
}

func (v version) String() string {
	return fmt.Sprintf("R%d-%d.%d.%d", v.r, v.x, v.y, v.z)
}

// GetLatestBuildWithPrefix finds the latest build with the given prefix on gs://chromeos-image-archive.
func GetLatestBuildWithPrefix(ctx context.Context, c *storage.Client, board, prefix string) (string, error) {
	fullPrefix := fmt.Sprintf("%s-release/%s", board, prefix)

	q := &storage.Query{
		Delimiter: "/",
		Prefix:    fullPrefix,
	}
	if err := q.SetAttrSelection([]string{"Name"}); err != nil {
		panic("SetAttrSelection failed")
	}
	objects := c.Bucket("chromeos-image-archive").Objects(ctx, q)

	var latestVersion version
	for {
		attrs, err := objects.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return "", fmt.Errorf("cannot get releases available for gs://chromeos-image-archive/%s", fullPrefix)
		}
		v, err := parseVersion(path.Base(attrs.Prefix))
		if err != nil {
			log.Println(err)
			continue
		}
		if latestVersion.less(v) {
			latestVersion = v
		}
	}
	if latestVersion == (version{}) {
		return "", fmt.Errorf("no releases available found for gs://chromeos-image-archive/%s", fullPrefix)
	}
	return latestVersion.String(), nil
}

// GetLatestReleaseForBoard finds the latest release for board on gs://chromeos-image-archive.
func GetLatestReleaseForBoard(ctx context.Context, c *storage.Client, board string) (string, error) {
	object := c.Bucket("chromeos-image-archive").Object(fmt.Sprintf("%s-release/LATEST-main", board))
	r, err := object.NewReader(ctx)
	if err != nil {
		return "", fmt.Errorf("cannot open %s: %w", misc.GsURI(object), err)
	}

	release, err := io.ReadAll(r)
	if err != nil {
		return "", fmt.Errorf("cannot read from %s: %w", misc.GsURI(object), err)
	}

	return string(release), nil
}

func getFlashTarget(ctx context.Context, c *storage.Client, board string, opts *Options) (targetBucket string, targetDirectory string, err error) {
	if opts.GS != "" {
		url, err := url.Parse(opts.GS)
		if err != nil {
			return "", "", err
		}
		return url.Host, strings.TrimPrefix(url.RequestURI(), "/"), nil
	}

	var prefix string
	if opts.ReleaseString != "" {
		prefix = "R" + opts.ReleaseString
	} else if opts.ReleaseNum != 0 {
		prefix = fmt.Sprintf("R%d-", opts.ReleaseNum)
	}

	var gsRelease string
	if prefix == "" {
		gsRelease, err = GetLatestReleaseForBoard(ctx, c, board)
	} else {
		gsRelease, err = GetLatestBuildWithPrefix(ctx, c, board, prefix)
	}

	return "chromeos-image-archive", fmt.Sprintf("%s-release/%s", board, gsRelease), err
}
