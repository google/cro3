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
	"golang.org/x/exp/slices"
	"google.golang.org/api/iterator"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/dut"
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/misc"
)

// version like R{r}-{x}.{y}.{z} e.g. R109-15236.80.0
//
// In fflash, we refer to those as:
//
//	R109-15236.80.0
//	 --- ----- -- -
//	 |   |     |  |
//	 |   |     |  Patch number
//	 |   |     Branch number
//	 |   Build number
//	 Milestone number
//
// The full string is called the version.
type version struct {
	r int // Milestone number
	x int // Build number
	y int // Branch number
	z int // Patch number
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

func queryPrefix(ctx context.Context, c *storage.Client, q *storage.Query) ([]*storage.ObjectAttrs, error) {
	var result []*storage.ObjectAttrs

	if err := q.SetAttrSelection([]string{"Name"}); err != nil {
		panic("SetAttrSelection failed")
	}
	objects := c.Bucket("chromeos-image-archive").Objects(ctx, q)
	for {
		attrs, err := objects.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("error while executing query: %w", err)
		}
		result = append(result, attrs)
	}
	return result, nil
}

func checkVersion(ctx context.Context, c *storage.Client, board string, v version) error {
	for _, file := range dut.Images {
		object := c.Bucket("chromeos-image-archive").Object(fmt.Sprintf("%s-release/%s/%s", board, v, file))
		_, err := object.Attrs(ctx)
		if err != nil {
			return fmt.Errorf("%s: %v", misc.GsURI(object), err)
		}
	}
	return nil
}

// GetLatestVersionWithPrefix finds the latest build with the given prefix on gs://chromeos-image-archive.
func GetLatestVersionWithPrefix(ctx context.Context, c *storage.Client, board, prefix string) (string, error) {
	fullPrefix := fmt.Sprintf("%s-release/%s", board, prefix)

	q := &storage.Query{
		Delimiter: "/",
		Prefix:    fullPrefix,
	}
	objects, err := queryPrefix(ctx, c, q)
	if err != nil {
		return "", fmt.Errorf("cannot get versions available for gs://chromeos-image-archive/%s*", fullPrefix)
	}

	var versions []version
	for _, attrs := range objects {
		v, err := parseVersion(path.Base(attrs.Prefix))
		if err != nil {
			log.Printf("Cannot parse %q, ignoring: %v", attrs.Prefix, err)
			continue
		}
		versions = append(versions, v)
	}

	slices.SortFunc(versions, func(a, b version) bool { return b.less(a) })
	for _, v := range versions {
		if err := checkVersion(ctx, c, board, v); err != nil {
			log.Printf("ignoring version %q: %v", v, err)
			continue
		}
		return v.String(), nil
	}
	return "", fmt.Errorf("no versions found for gs://chromeos-image-archive/%s*", fullPrefix)
}

// getLatestVersionForLATEST finds the latest version for LATEST file for board on gs://chromeos-image-archive.
// If isPrefix is true, looks for the LATEST files having the {latest} as their prefix.
func getLatestVersionForLATEST(ctx context.Context, c *storage.Client, board string, latest string, isPrefix bool) (string, error) {
	name := fmt.Sprintf("%s-release/%s", board, latest)
	var objects []*storage.ObjectAttrs
	if isPrefix {
		var err error
		q := &storage.Query{Prefix: name}
		objects, err = queryPrefix(ctx, c, q)
		if err != nil {
			return "", fmt.Errorf("cannot get LATEST file from gs://chromeos-image-archive/%s*", name)
		}
	} else {
		objects = []*storage.ObjectAttrs{
			{
				Name: name,
			},
		}
	}

	var latestVersion version
	for _, attrs := range objects {
		latestFileObj := c.Bucket("chromeos-image-archive").Object(attrs.Name)
		r, err := latestFileObj.NewReader(ctx)
		if err != nil {
			return "", fmt.Errorf("cannot open LATEST file %s: %w", misc.GsURI(latestFileObj), err)
		}
		rawVersion, err := io.ReadAll(r)
		if err != nil {
			return "", fmt.Errorf("cannot read from LATEST file %s: %w", misc.GsURI(latestFileObj), err)
		}
		version, err := parseVersion(string(rawVersion))
		if err != nil {
			return "", fmt.Errorf("cannot parse LATEST file %s: %w", misc.GsURI(latestFileObj), err)
		}
		if latestVersion.less(version) {
			latestVersion = version
		}
	}

	if latestVersion == (version{}) {
		return "", fmt.Errorf("no LATEST file found for gs://chromeos-image-archive/%s*", name)
	}
	return latestVersion.String(), nil
}

// GetLatestVersionForMilestone finds the latest version for board and milestone on gs://chromeos-image-archive.
func GetLatestVersionForMilestone(ctx context.Context, c *storage.Client, board string, milestone int) (string, error) {
	version, err := getLatestVersionForLATEST(ctx, c, board, fmt.Sprintf("LATEST-release-R%d-", milestone), true)
	if err != nil {
		log.Printf("%v, maybe the milestone is not branched yet. Retrying with prefix matching", err)
		version, err = GetLatestVersionWithPrefix(ctx, c, board, fmt.Sprintf("R%d-", milestone))
	}
	return version, err
}

// GetLatestVersion finds the latest version for board on gs://chromeos-image-archive.
func GetLatestVersion(ctx context.Context, c *storage.Client, board string) (string, error) {
	return getLatestVersionForLATEST(ctx, c, board, "LATEST-main", false)
}

func getFlashTarget(ctx context.Context, c *storage.Client, board string, opts *Options) (targetBucket string, targetDirectory string, err error) {
	if opts.GS != "" {
		url, err := url.Parse(opts.GS)
		if err != nil {
			return "", "", err
		}
		return url.Host, strings.TrimPrefix(url.RequestURI(), "/"), nil
	}

	var gsVersion string
	if opts.VersionString != "" {
		gsVersion, err = GetLatestVersionWithPrefix(ctx, c, board, opts.VersionString)
	} else if opts.MilestoneNum != 0 {
		gsVersion, err = GetLatestVersionForMilestone(ctx, c, board, opts.MilestoneNum)
	} else {
		gsVersion, err = GetLatestVersion(ctx, c, board)
	}

	return "chromeos-image-archive", fmt.Sprintf("%s-release/%s", board, gsVersion), err
}
