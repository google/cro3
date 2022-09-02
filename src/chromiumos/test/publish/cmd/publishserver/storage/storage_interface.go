// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package storage

import (
	"context"
	"fmt"
	"io"
	"os"
	"time"

	"cloud.google.com/go/storage"
	"google.golang.org/api/option"
)

// This file exists to provide a mockable interface to the google storage client
type StorageClientInterface interface {
	Close()
	Write(ctx context.Context, filePath string, gsObject GSObject) error
}

type StorageClient struct {
	client *storage.Client
}

func NewStorageClientWithCredsFile(ctx context.Context, credentialsFile string) (*StorageClient, error) {
	client, err := storage.NewClient(ctx, option.WithCredentialsFile(credentialsFile))
	if err != nil {
		return nil, err
	}
	return &StorageClient{
		client: client,
	}, nil
}

func NewStorageClientWithDefaultAccount(ctx context.Context) (*StorageClient, error) {
	client, err := storage.NewClient(ctx)
	if err != nil {
		return nil, err
	}
	return &StorageClient{
		client: client,
	}, nil
}

// Write a single file to GCS.
func (c *StorageClient) Write(ctx context.Context, filePath string, gsObject GSObject) error {
	// Open local file.
	f, err := os.Open(filePath)
	if err != nil {
		return fmt.Errorf("unable to open local files %s, %w", filePath, err)
	}
	defer f.Close()

	ctx, cancel := context.WithTimeout(ctx, time.Second*60)
	defer cancel()

	wc := c.client.Bucket(gsObject.Bucket).Object(gsObject.Object).NewWriter(ctx)
	if _, err := io.Copy(wc, f); err != nil {
		return fmt.Errorf("failed file copy for local file %s, %w", filePath, err)
	}
	if err := wc.Close(); err != nil {
		return fmt.Errorf("failed to close writer: %w", err)
	}
	return nil
}

func (c *StorageClient) Close() {
	c.client.Close()
}
