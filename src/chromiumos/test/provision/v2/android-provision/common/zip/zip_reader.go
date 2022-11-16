// Copyright 2022 The Chromium Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package zip

import (
	"archive/zip"
	"io"
	"os"
	"path/filepath"
	"strings"
)

type ZipReader interface {
	UnzipFile(s, d string) error
}

type Zip struct {
}

func (z *Zip) UnzipFile(srcFile, dstPath string) error {
	r, e := zip.OpenReader(srcFile)
	if e != nil {
		return e
	}
	defer r.Close()
	for _, f := range r.File {
		if f.FileInfo().IsDir() {
			os.MkdirAll(filepath.Join(dstPath, f.Name), os.ModePerm)
			continue
		}
		filePath := filepath.Join(dstPath, strings.ToLower(f.Name))
		if err := os.MkdirAll(filepath.Dir(filePath), os.ModePerm); err != nil {
			return err
		}
		var err error
		var dstFile *os.File
		if dstFile, err = os.OpenFile(filePath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, f.Mode()); err == nil {
			var fileInArchive io.ReadCloser
			if fileInArchive, err = f.Open(); err == nil {
				_, err = io.Copy(dstFile, fileInArchive)
				fileInArchive.Close()
			}
			dstFile.Close()
		}
		if err != nil {
			return err
		}
	}
	return nil
}
