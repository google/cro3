// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"context"
	"fmt"
	"io"
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

func GetLatestBuildForChannel(ctx context.Context, c *storage.Client, board, channel string) (string, error) {
	q := &storage.Query{
		Delimiter: "/",
		Prefix:    fmt.Sprintf("%s-channel/%s/", channel, board),
	}
	if err := q.SetAttrSelection([]string{"Name"}); err != nil {
		panic("SetAttrSelection failed")
	}
	objects := c.Bucket("chromeos-releases").Objects(ctx, q)

	v := ""
	for {
		attrs, err := objects.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return "", fmt.Errorf("cannot get latest for channel=%s, board=%s: %s", channel, board, err)
		}
		v = maxVersion(v, path.Base(attrs.Prefix))
	}
	if v == "" {
		return "", fmt.Errorf("no versions found for channel=%s, board=%s", channel, board)
	}
	return v, nil
}

func GetReleaseForBuild(ctx context.Context, c *storage.Client, board, build string) (string, error) {
	object := c.Bucket("chromeos-image-archive").Object(fmt.Sprintf("%s-release/LATEST-%s", board, build))
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
