// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package fileutils defines generic file utilities.
package fileutils

import (
	"context"
	"crypto/sha256"
	"fmt"
	"io"
	"io/fs"
	"io/ioutil"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"strings"
	"time"

	"chromiumos/platform/dev/contrib/cros_openwrt/image_builder/log"
)

const pendingDownloadFileSuffix = ".downloading"

// DefaultDirPermissions defines the default directory permissions to use when
// creating new directories.
const DefaultDirPermissions fs.FileMode = 0777

const pathTimestampTimeFormat = "20060102-150405"

// CleanDirectory removes all files within the directory at dirPath.
func CleanDirectory(dirPath string) error {
	log.Logger.Printf("Cleaning dir %q\n", dirPath)
	files, err := ioutil.ReadDir(dirPath)
	if err != nil {
		return fmt.Errorf("failed to read contents of directory %q: %w", dirPath, err)
	}
	for _, f := range files {
		fullPath := path.Join(dirPath, f.Name())
		if err := os.RemoveAll(fullPath); err != nil {
			return fmt.Errorf("failed to remove %q: %w", fullPath, err)
		}
	}
	return nil
}

// DownloadFileFromURL downloads a file from the src URL and saves it into the
// directory at path dstFolder.
// The last path part of src is used as the filename.
// If a file with the same name is already present in the destination folder,
// the download is skipped and no files are modified.
func DownloadFileFromURL(ctx context.Context, src, dstFolder string) (string, error) {
	// Parse src for filename.
	srcURL, err := url.Parse(src)
	if err != nil {
		return "", fmt.Errorf("failed to parse src URL %q: %w", src, err)
	}
	src = srcURL.String()
	pathSegments := strings.Split(srcURL.Path, "/")
	fileName := pathSegments[len(pathSegments)-1]
	dstFilePath := path.Join(dstFolder, fileName)

	// Do not re-download if file already exists, just re-use it.
	if _, err := os.Stat(dstFilePath); err == nil {
		log.Logger.Printf("Skipping download of %q, previous download exists at %q", src, dstFilePath)
		return dstFilePath, nil
	}

	// Download to temp file, then rename when complete.
	pendingDownloadFilePath := dstFilePath + pendingDownloadFileSuffix
	dstFile, err := os.Create(pendingDownloadFilePath)
	if err != nil {
		return "", fmt.Errorf("failed to create temporary download file at %q: %w", pendingDownloadFilePath, err)
	}
	downloadSuccessful := false
	defer func() {
		_ = dstFile.Close()
		if !downloadSuccessful {
			_ = os.Remove(pendingDownloadFilePath)
		}
	}()
	req, err := http.NewRequestWithContext(ctx, "GET", src, nil)
	if err != nil {
		return "", fmt.Errorf("failed build HTTP GET request to download from URL %q: %w", src, err)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed request to download from URL %q: %w", src, err)
	}
	defer func() {
		_ = resp.Body.Close()
	}()
	if _, err := io.Copy(dstFile, resp.Body); err != nil {
		return "", fmt.Errorf("failed to download file from %q to %q: %w", src, pendingDownloadFilePath, err)
	}
	if err := os.Rename(pendingDownloadFilePath, dstFilePath); err != nil {
		return "", fmt.Errorf("failed to rename %q to %q after completed download from %q: %w", pendingDownloadFilePath, dstFile, src, err)
	}
	downloadSuccessful = true

	return dstFilePath, nil
}

// GetLatestFilePathInDir returns the path of the file with the latest
// modification time in the directory at path dirPath.
func GetLatestFilePathInDir(dirPath string) (string, error) {
	files, err := ioutil.ReadDir(dirPath)
	if err != nil {
		return "", fmt.Errorf("failed to read files in dir %q: %w", dirPath, err)
	}
	var latestFile os.FileInfo
	for _, file := range files {
		if file.Mode().IsRegular() && (latestFile == nil || latestFile.ModTime().Before(file.ModTime())) {
			latestFile = file
		}
	}
	if latestFile == nil {
		return "", fmt.Errorf("no files found in dir %q", dirPath)
	}
	return filepath.Join(dirPath, latestFile.Name()), nil
}

// ContextualReaderWrapper is a wrapper around an existing io.Reader that allows
// for the interruption of reads with the cancellation of a context.
type ContextualReaderWrapper struct {
	ctx    context.Context
	reader io.Reader
}

// NewContextualReaderWrapper initializes a new ContextualReaderWrapper.
func NewContextualReaderWrapper(ctx context.Context, reader io.Reader) *ContextualReaderWrapper {
	return &ContextualReaderWrapper{
		ctx:    ctx,
		reader: reader,
	}
}

// Read calls io.Reader.Read on the wrapped reader, allowing for interruption
// from a cancellation of the context.
func (c *ContextualReaderWrapper) Read(p []byte) (n int, err error) {
	readChan := make(chan error)
	go func() {
		readChan <- func() error {
			n, err = c.reader.Read(p)
			return err
		}()
	}()
	select {
	case <-c.ctx.Done():
		err = c.ctx.Err()
		break
	case err = <-readChan:
		break
	}
	return n, err
}

// ContextualWriterWrapper is a wrapper around an existing io.Writer that allows
// for the interruption of writes with the cancellation of a context.
type ContextualWriterWrapper struct {
	ctx    context.Context
	writer io.Writer
}

// NewContextualWriterWrapper initializes a new ContextualWriterWrapper.
func NewContextualWriterWrapper(ctx context.Context, writer io.Writer) *ContextualWriterWrapper {
	return &ContextualWriterWrapper{
		ctx:    ctx,
		writer: writer,
	}
}

// Write calls Write on the wrapped writer, allowing for interruption from
// a cancellation of the context.
func (c *ContextualWriterWrapper) Write(p []byte) (n int, err error) {
	writeChan := make(chan error)
	go func() {
		writeChan <- func() error {
			n, err = c.writer.Write(p)
			return err
		}()
	}()
	select {
	case <-c.ctx.Done():
		err = c.ctx.Err()
		break
	case err = <-writeChan:
		break
	}
	return n, err
}

// UnpackTarXz unpacks the contents of a tar archive file compressed with xz
// (*.tar.xz files) at archivePath into the directory at path outDir.
func UnpackTarXz(ctx context.Context, archivePath string, outDir string) error {
	cmd := exec.CommandContext(ctx, "tar", "-Jxf", archivePath, "-C", outDir, "--strip-components", "1")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to unpack tar.xz archive %q to %q: %w", archivePath, outDir, err)
	}
	return nil
}

// PackageTarXz packages the contents of a directory into a tar file compressed
// with xz.
func PackageTarXz(ctx context.Context, srcDir, dstArchivePath string) error {
	relativeSrcPaths, err := os.ReadDir(srcDir)
	if err != nil {
		return fmt.Errorf("failed to read dir %q: %w", srcDir, err)
	}
	tarArgs := []string{"-Jcf", dstArchivePath}
	for _, filePath := range relativeSrcPaths {
		tarArgs = append(tarArgs, filePath.Name())
	}
	cmd := exec.CommandContext(ctx, "tar", tarArgs...)
	cmd.Dir = srcDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to pack tar.xz archive files in %q to %q: %w", srcDir, dstArchivePath, err)
	}
	return nil
}

// CopyFile copies the file or directory at srcFilePath to dstPath. If dstPath
// is a directory, the file is placed within it.
func CopyFile(ctx context.Context, srcFilePath string, dstPath string) error {
	cmd := exec.CommandContext(ctx, "cp", "-R", srcFilePath, dstPath)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to copy file %q to dir %q: %w", srcFilePath, dstPath, err)
	}
	return nil
}

// CopyFilesInDirToDir copies all files in directory at path srcDirPath into
// the directory at dstDirPath.
func CopyFilesInDirToDir(ctx context.Context, srcDirPath string, dstDirPath string) error {
	cmd := exec.CommandContext(ctx, "bash", "cp", "-R", path.Join(srcDirPath, "*"), dstDirPath)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	files, err := ioutil.ReadDir(srcDirPath)
	if err != nil {
		return fmt.Errorf("failed to list files in dir %q: %w", srcDirPath, err)
	}
	for _, file := range files {
		filePath := path.Join(srcDirPath, file.Name())
		if err := CopyFile(ctx, filePath, dstDirPath); err != nil {
			return fmt.Errorf("failed to copy files in dir %q to dir %q: %w", srcDirPath, dstDirPath, err)
		}
	}
	return nil
}

// DirectoryExists checks if dirPath refers to an existing directory.
func DirectoryExists(dirPath string) (bool, error) {
	stat, err := os.Stat(dirPath)
	if os.IsNotExist(err) {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("failed to stat dirPath %q: %w", dirPath, err)
	}
	if !stat.IsDir() {
		return false, fmt.Errorf("file at %q exists but is not a directory", dirPath)
	}
	return true, nil
}

// AssertDirectoriesExist checks each directory path in dirs to validate that
// it exists and is a directory. Returns nil only if the assertion is true for
// all paths.
func AssertDirectoriesExist(dirs ...string) error {
	for _, dir := range dirs {
		exists, err := DirectoryExists(dir)
		if err != nil || !exists {
			if err == nil {
				err = fmt.Errorf("directory does not exist")
			}
			return fmt.Errorf("failed directory existence assertion for path %q: %w", dir, err)
		}
	}
	return nil
}

// WriteStringToFile writes input string to file.
// Directories in path are created if they do not exist.
// Existing file contents are overwritten.
func WriteStringToFile(ctx context.Context, input string, outFilePath string) error {
	outFileDir := path.Dir(outFilePath)
	if outFileDir != "" {
		if err := os.MkdirAll(outFileDir, DefaultDirPermissions); err != nil {
			return fmt.Errorf("failed to make dirs for file %q: %w", outFilePath, err)
		}
	}
	outFile, err := os.Create(outFilePath)
	if err != nil {
		return fmt.Errorf("failed to create file %q: %w", outFilePath, err)
	}
	defer func() {
		_ = outFile.Close()
	}()
	outFileWriter := NewContextualWriterWrapper(ctx, outFile)
	if _, err := outFileWriter.Write([]byte(input)); err != nil {
		return fmt.Errorf("failed to write to file %q: %w", outFilePath, err)
	}
	return nil
}

// BuildFileChecksumSHA256 builds and returns SHA256 checksum of the contents of the
// file at filePath.
func BuildFileChecksumSHA256(ctx context.Context, filePath string) (string, error) {
	inFile, err := os.Open(filePath)
	if err != nil {
		return "", fmt.Errorf("failed to open file %q: %w", filePath, err)
	}
	defer func() {
		_ = inFile.Close()
	}()
	inFileReader := NewContextualReaderWrapper(ctx, inFile)
	hash := sha256.New()
	if _, err := io.Copy(hash, inFileReader); err != nil {
		return "", fmt.Errorf("failed to hash contents of file %q: %w", filePath, err)
	}
	checksum := fmt.Sprintf("%x", hash.Sum(nil))
	return checksum, err
}

// CollectFileChecksums walks a directory and collects checksums for every
// found file. Checksums are returned in a map of relative file path to
// checksum string.
func CollectFileChecksums(ctx context.Context, dirPath string) (map[string]string, error) {
	filePathToChecksum := make(map[string]string)
	dirPath = path.Clean(dirPath)
	if err := filepath.Walk(dirPath, func(filePath string, info fs.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}
		checksum, err := BuildFileChecksumSHA256(ctx, filePath)
		if err != nil {
			return fmt.Errorf("failed to build checksum of file %q: %w", filePath, err)
		}
		relativePath := strings.TrimPrefix(strings.TrimPrefix(filePath, dirPath), "/")
		filePathToChecksum[relativePath] = checksum
		return nil
	}); err != nil {
		return nil, fmt.Errorf("failed to collect file checksums from dir %q: %w", dirPath, err)
	}

	return filePathToChecksum, nil
}

// BuildTimestampForFilePath returns a human-readable, file path compatible
// timestamp of time.
func BuildTimestampForFilePath(time time.Time) string {
	return time.Format(pathTimestampTimeFormat)
}
