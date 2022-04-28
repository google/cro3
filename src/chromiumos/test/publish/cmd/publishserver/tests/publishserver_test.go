// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tests

import (
	"context"
	"fmt"
	"io/ioutil"
	"os"
	"path"
	"testing"

	"chromiumos/test/publish/cmd/publishserver/mock_storage"
	"chromiumos/test/publish/cmd/publishserver/storage"

	"github.com/golang/mock/gomock"
)

func TestGSUploadMultiFile(t *testing.T) {
	/*Manual Equivalent"
	gsc, err := storage.NewGSClient(context.Background(), "path_to_creds")
	if err != nil {
		t.Errorf("Failed %w", err)
	}
	if err = gsc.Upload(context.Background(), "source_path", "gs://dest"); err != nil {
		t.Errorf("Failed %w", err)
	}
	*/

	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sci := mock_storage.NewMockStorageClientInterface(ctrl)
	client := storage.NewGSTestClient(sci)

	root, err := createTempUploadDir()
	if err != nil {
		t.Errorf("failed setup, %v", err)
	}

	rootBucket := storage.GSObject{
		Bucket: "some_bucket",
		Object: "",
	}

	sci.EXPECT().Write(gomock.Any(), path.Join(root, "file1"), rootBucket.Extend("file1")).Return(nil)
	sci.EXPECT().Write(gomock.Any(), path.Join(root, "file2"), rootBucket.Extend("file2")).Return(nil)
	sci.EXPECT().Write(gomock.Any(), path.Join(root, "dir1/dir2/file3"), rootBucket.Extend("dir1/dir2/file3")).Return(nil)

	client.Upload(context.Background(), root, "gs://some_bucket")
}

func TestGSUploadOneFile(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	sci := mock_storage.NewMockStorageClientInterface(ctrl)
	client := storage.NewGSTestClient(sci)

	root, err := createTempUploadDir()
	if err != nil {
		t.Errorf("failed setup, %v", err)
	}

	rootBucket := storage.GSObject{
		Bucket: "some_bucket",
		Object: "one_file",
	}

	sci.EXPECT().Write(gomock.Any(), path.Join(root, "file1"), rootBucket.Extend("file1")).Return(nil)

	client.Upload(context.Background(), path.Join(root, "file1"), "gs://some_bucket/one_file")
}

// createTempUploadDir creates fake files to "upload"
func createTempUploadDir() (string, error) {
	root, err := ioutil.TempDir("/tmp", "upload_unit_test_dir")
	if err != nil {
		return "", err
	}

	_, err = os.Create(path.Join(root, "file1"))
	if err != nil {
		return "", fmt.Errorf("unable to create first directory, %w", err)
	}
	_, err = os.Create(path.Join(root, "file2"))
	if err != nil {
		return "", fmt.Errorf("unable to create second directory, %w", err)
	}

	if err := os.MkdirAll(path.Join(root, "dir1/dir2"), 0777); err != nil {
		return "", fmt.Errorf("unable to create nested folders, %w", err)
	}
	_, err = os.Create(path.Join(root, "dir1/dir2/file3"))
	if err != nil {
		return "", fmt.Errorf("unable to create third directory, %w", err)
	}

	return root, nil
}
