// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"fmt"
	"io"
	"log"
	"os"
	"path"
	"strings"
	"time"

	"cloud.google.com/go/storage"
	"github.com/google/uuid"
)

const cacheSize = 128

type Cache struct {
	location    string
	pathToLocal *LRU
	gcsClient   *storage.Client
}

func MakeCache(location string) (*Cache, error) {
	log.Printf("creating cache on location %s", location)
	ctx := context.Background()
	client, err := storage.NewClient(ctx)
	if err != nil {
		return nil, fmt.Errorf("could not instantiate GCS client, %w", err)
	}

	lru, _ := MakeLRU(cacheSize, deleteFileCallback)

	return &Cache{
		location:    location,
		pathToLocal: lru,
		gcsClient:   client,
	}, nil
}

func MakeCacheFromexisting(location string) *Cache {
	// TODO(jaquesc): option to reuse local cache on server restart
	return nil
}

// Get retrieves the local path to the gsPath. If none exist, download.
func (c *Cache) Get(gsPath string) (string, error) {
	log.Printf("attempting to fetch %s from cache", gsPath)
	if c.pathToLocal.Exists(gsPath) {
		localPath, err := c.pathToLocal.Get(gsPath)
		if err != nil {
			return "", err
		}
		log.Printf("%s already cached at location %s", gsPath, localPath)
		return localPath, nil
	}
	localPath := path.Join(c.location, uuid.New().String())
	log.Printf("%s not cached, retrieving at %s", gsPath, localPath)
	if err := c.fetchFromGS(gsPath, localPath); err != nil {
		log.Printf("error when fetching from gs", err)
		return "", err
	}
	log.Printf("successfully downloaded %s", gsPath)

	// storing in local cache
	c.pathToLocal.Add(gsPath, localPath)
	return localPath, nil
}

// fetchFromGS downloads a file from gsPath onto the local URI localPath
func (c *Cache) fetchFromGS(gsPath, localPath string) error {
	bucket, object, err := c.parseGSURL(gsPath)
	if err != nil {
		return fmt.Errorf("failed to parse gs url, %w", err)
	}

	ctx := context.Background()
	ctx, cancel := context.WithTimeout(ctx, time.Second*300)
	defer cancel()

	log.Printf("Fetching object %s from bucket %s", object, bucket)
	rc, err := c.gcsClient.Bucket(bucket).Object(object).NewReader(ctx)
	if err != nil {
		return fmt.Errorf("could not get a reader for GCS object %q in bucket %q, %w", object, bucket, err)
	}
	defer rc.Close()

	wf, err := os.Create(localPath)
	if err != nil {
		return fmt.Errorf("could not create local file %s, %w", localPath, err)
	}

	defer wf.Close()

	if _, err := io.Copy(wf, rc); err != nil {
		return fmt.Errorf("could not download gcs file, %w", err)
	}

	return nil
}

// parseGSURL retrieves the bucket and object from a GS URL.
// URL expectation is of the form: "bucket/object"
// This method does not exists in the GS client, so creating bespoke.
func (c *Cache) parseGSURL(gsUrl string) (string, string, error) {
	if strings.HasPrefix(gsUrl, "gs://") {
		return "", "", fmt.Errorf("gs url must not have \"gs://\" prefix")
	}
	r := strings.SplitN(gsUrl, "/", 2)
	if len(r) != 2 {
		return "", "", fmt.Errorf("gs url must contain both a bucket and object")
	}
	return r[0], r[1], nil
}

// Close cleans up the cache (deletes files).
func (c *Cache) Close() {
	log.Println("cleaning up cache.")
	defer c.gcsClient.Close()
	c.pathToLocal.Delete()
}

// deleteFileCallback acts as the callback for what the LRU needs to do on item
// deletion.
func deleteFileCallback(key, value string) {
	log.Printf("deleting file %s", value)
	if err := os.Remove(value); err != nil {
		log.Fatalf("Could not delete %s because %v", value, err)
	}
}
