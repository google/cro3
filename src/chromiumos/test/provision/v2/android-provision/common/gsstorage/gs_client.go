// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gsstorage

import (
	"context"
	"io"
	"os"
	"path/filepath"
	"time"

	"cloud.google.com/go/storage"

	"google.golang.org/api/iterator"
	"google.golang.org/api/option"

	"chromiumos/test/provision/v2/android-provision/common"
)

// GsClient specifies the APIs between provisioning service and storage client.
// GsClient interface is used mainly for testing purpose,
// since storage pkg does not provide test pkg.
type GsClient interface {
	// Upload uploads an apk to the Fleet Services caching service.
	Upload(ctx context.Context, apkLocalPath string, apkName string) error
	// ListFiles lists objects using prefix and delimeter.
	ListFiles(ctx context.Context, prefix, delim string) ([]string, error)
}

// gs is mainly used for testing purpose.
type gs struct {
	bucketName string
}

func NewGsClient(bucketName string) GsClient {
	return &gs{
		bucketName: bucketName,
	}
}

func (gs *gs) Upload(ctx context.Context, apkPath string, remotePath string) error {
	client, err := storage.NewClient(ctx, option.WithCredentialsFile(common.DroneServiceAccountCreds))
	if err != nil {
		return err
	}
	defer client.Close()
	f, err := os.Open(apkPath)
	if err != nil {
		return err
	}
	defer f.Close()
	// Cancel after 5m.
	ctx, cancel := context.WithTimeout(ctx, time.Minute*5)
	defer cancel()
	// Upload will be retried until context is canceled.
	o := client.Bucket(gs.bucketName).Object(remotePath).Retryer(storage.WithPolicy(storage.RetryAlways))
	// Only upload object if it does not already exist.
	o = o.If(storage.Conditions{DoesNotExist: true})
	wc := o.NewWriter(ctx)
	if _, err = io.Copy(wc, f); err != nil {
		return err
	}
	if err := wc.Close(); err != nil {
		return err
	}
	return nil
}

// GetGsPath return GS path to image files.
func GetGsPath(bucketName string, folders ...string) string {
	if bucketName == "" {
		bucketName = common.GSImageBucketName
	}
	return "gs://" + filepath.Join(append([]string{bucketName}, folders...)...) + "/"
}

func (gs *gs) ListFiles(ctx context.Context, prefix, delim string) ([]string, error) {
	client, err := storage.NewClient(ctx, option.WithCredentialsFile(common.DroneServiceAccountCreds))
	if err != nil {
		return nil, err
	}
	defer client.Close()
	ctx, cancel := context.WithTimeout(ctx, time.Minute)
	defer cancel()

	it := client.Bucket(gs.bucketName).Objects(ctx, &storage.Query{
		Prefix:     prefix,
		Delimiter:  delim,
		Projection: storage.ProjectionNoACL,
	})
	var names []string
	for {
		attrs, err := it.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return nil, err
		}
		// Filtering out current folder/prefix from listing.
		if name := attrs.Name; name != prefix {
			names = append(names, filepath.Base(name))
		}
	}
	return names, err
}
