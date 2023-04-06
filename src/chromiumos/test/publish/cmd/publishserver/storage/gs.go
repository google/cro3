// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package storage

import (
	"context"
	"fmt"
	"io/fs"
	"log"
	"net/url"
	"os"
	"path"
	"path/filepath"
	"strings"

	"go.chromium.org/luci/common/sync/parallel"
)

const maxConcurrentUploads = 10

// For testing
type GSClientInterface interface {
	Upload(ctx context.Context, localFolder string, gsUrl string) error
	Close()
}

type GSClient struct {
	client StorageClientInterface
}

// Storage metadata for local file
type LocalObject struct {
	FullPath string
	RelPath  string
}

// Storage metadata for remote file
type GSObject struct {
	Bucket string
	Object string
}

// Extend adds addendum to the end of object for a GSObject
func (o *GSObject) Extend(addendum string) GSObject {
	return GSObject{
		Bucket: o.Bucket,
		Object: path.Join(o.Object, addendum),
	}
}

func NewGSClient(ctx context.Context, credentialsFile string) (*GSClient, error) {
	var client *StorageClient
	var err error
	if credentialsFile != "" {
		client, err = NewStorageClientWithCredsFile(ctx, credentialsFile)
		if err != nil {
			return nil, err
		}
	} else {
		client, err = NewStorageClientWithDefaultAccount(ctx)
		if err != nil {
			return nil, err
		}
	}

	return &GSClient{
		client: client,
	}, nil
}

func NewGSTestClient(client StorageClientInterface) *GSClient {
	return &GSClient{
		client: client,
	}
}

func (c *GSClient) Close() {
	c.client.Close()
}

// Upload uploads localFolder (which may be a file) to designated gsURL
// uploads here are done in parallel
func (c *GSClient) Upload(ctx context.Context, localFolder string, gsUrl string) error {
	log.Printf("Starting upload of %s to %s", localFolder, gsUrl)
	rootObject, err := c.parseGSURL(gsUrl)
	if err != nil {
		return fmt.Errorf("unable to parse gs url, %w", err)
	}
	log.Printf("Parsed URL: %s", rootObject)

	allFiles, err := c.getAllFilesInFolderRecursively(localFolder)
	if err != nil {
		return fmt.Errorf("unable to get local files, %w", err)
	}
	log.Printf("Uploading files (max %d workers): %s", maxConcurrentUploads, allFiles)

	uploadOne := func(currentFile LocalObject) error {
		currentObject := rootObject.Extend(currentFile.RelPath)
		if err := c.client.Write(ctx, currentFile.FullPath, currentObject); err != nil {
			return fmt.Errorf("failed upload for file %s to %s, %w", currentFile, gsUrl, err)
		}
		return nil
	}

	// timeout error
	var terr error
	err = parallel.WorkPool(maxConcurrentUploads, func(items chan<- func() error) {
		for _, aFile := range allFiles {
			// Create a loop-local variable for capture in the lambda.
			f := aFile
			item := func() error {
				return uploadOne(f)
			}
			// Check the context timeout when adding files to the stack.
			select {
			case <-ctx.Done():
				terr = ctx.Err()
				return
			default:
				items <- item
			}
		}
	})
	if terr != nil {
		return terr
	}

	return err
}

// parseGSURL retrieves the bucket and object from a GS URL.
// URL expectation is of the form: "gs://bucket/object"
// This method does not exists in the GS client, so creating bespoke.
func (c *GSClient) parseGSURL(gsUrl string) (*GSObject, error) {
	if !strings.HasPrefix(gsUrl, "gs://") {
		return nil, fmt.Errorf("gs url must begin with 'gs://', instead have, %s", gsUrl)
	}

	u, err := url.Parse(gsUrl)
	if err != nil {
		return nil, fmt.Errorf("unable to parse url, %w", err)
	}

	// Host corresponds to bucket
	// Path corresponds to object (though we need to remove prepending '/')
	return &GSObject{
		Bucket: u.Host,
		Object: cleanObjectPath(u.Path),
	}, nil
}

// cleanObjectPath removes the first slash in a path if any. The built-in path
// framework concerns itself with removing trailing only, and as such we do so
// bespoke.
func cleanObjectPath(objectPath string) string {
	if strings.HasPrefix(objectPath, "/") {
		return objectPath[1:]
	}
	return objectPath
}

// getAllFilesInFolderRecursively retrieves all files within a current folder.
// If a file is input instead, just return the file itself.
func (c *GSClient) getAllFilesInFolderRecursively(localFolder string) ([]LocalObject, error) {
	fi, err := os.Stat(localFolder)
	if err != nil {
		return nil, fmt.Errorf("could not find file %w", err)
	}
	if !fi.IsDir() && fi.Mode()&fs.ModeSymlink == 0 {
		return []LocalObject{{
			FullPath: localFolder,
			RelPath:  localFolder[len(path.Dir(localFolder))+1:],
		}}, nil
	}

	var files []LocalObject
	err = filepath.Walk(localFolder, func(currPath string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if !info.IsDir() && info.Mode()&fs.ModeSymlink == 0 {
			files = append(files, LocalObject{
				FullPath: currPath,
				RelPath:  currPath[len(path.Clean(localFolder))+1:],
			})
		}
		return nil
	})

	return files, err
}
