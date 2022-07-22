// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"context"
	"fmt"
	"io"
	"net/url"
	"path"

	"cloud.google.com/go/storage"
	"golang.org/x/mod/semver"
	"google.golang.org/api/iterator"
)

func maxVersion(v, w string) string {
	if semver.Compare(v, w) > 0 {
		return v
	}
	return w
}

// GetLatestBuildWithPrefix finds the latest build with the given prefix on gs://chromeos-image-archive.
// Versions are compared with semver.Compare.
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

	v := ""
	for {
		attrs, err := objects.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return "", fmt.Errorf("cannot get releases available for gs://chromeos-image-archive/%s", fullPrefix)
		}
		v = maxVersion(v, path.Base(attrs.Prefix))
	}
	if v == "" {
		return "", fmt.Errorf("no releases available found for gs://chromeos-image-archive/%s", fullPrefix)
	}
	return v, nil
}

// GetLatestReleaseForBoard finds the latest release for board on gs://chromeos-image-archive.
func GetLatestReleaseForBoard(ctx context.Context, c *storage.Client, board string) (string, error) {
	object := c.Bucket("chromeos-image-archive").Object(fmt.Sprintf("%s-release/LATEST-main", board))
	r, err := object.NewReader(ctx)
	if err != nil {
		return "", fmt.Errorf("cannot open %s: %s", gsURI(object), err)
	}

	release, err := io.ReadAll(r)
	if err != nil {
		return "", fmt.Errorf("cannot read from %s: %s", gsURI(object), err)
	}

	return string(release), nil
}

func getFlashTarget(ctx context.Context, c *storage.Client, board string, opts *Options) (targetBucket string, targetDirectory string, err error) {
	if opts.GS != "" {
		url, err := url.Parse(opts.GS)
		if err != nil {
			return "", "", err
		}
		return url.Host, url.RequestURI(), nil
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
