// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package dirs defines the working and source directories used by
// cros_openwrt_image_builder.
package dirs

import (
	"fmt"
	"os"
	"path/filepath"

	"chromiumos/platform/dev/contrib/cros_openwrt/image_builder/fileutils"
	"chromiumos/platform/dev/contrib/cros_openwrt/image_builder/log"
)

const defaultWorkingDirPath = "/tmp/cros_openwrt_image_builder"

// WorkingDirectory defines related working directories and provides functions
// for cleaning them.
type WorkingDirectory struct {
	// BaseDirPath is the base working directory containing all other working
	// subdirectories.
	BaseDirPath string

	// SdkDownloadsDirPath is the path to the directory where sdk archives are
	// downloaded to.
	// Checked before downloading new archives.
	SdkDownloadsDirPath string

	// ImageBuilderDownloadsDirPath is the path to the directory where image
	// builder archives are downloaded to.
	// Checked before downloading new archives.
	ImageBuilderDownloadsDirPath string

	// SdkDirPath is the path to the directory where the current sdk is extracted
	// to or installed which is used for preforming sdk operations.
	// Will be cleared upon switching sdks.
	SdkDirPath string

	// ImageBuilderDirPath is the path to the directory where the current image
	// builder is extracted to or installed which is used for preforming image
	// builder operations.
	// Will be cleared upon switching image builders.
	ImageBuilderDirPath string

	// ImageBuilderIncludedFilesDirPath is the path to the temporary directory
	// used to store a copy of SrcDirectory.IncludedImagesFilesDirPath during the
	// building process, allowing for adding generated files and evaluating file
	// checksums.
	// Will be cleared before image building.
	ImageBuilderIncludedFilesDirPath string

	// PackagesOutputDirPath is the path to the directory where custom packages
	// built using the sdk are stored.
	// Will be cleared when new packages are created.
	PackagesOutputDirPath string

	// ImagesOutputDirPath is the path to the directory where custom images built
	// using the image builder are stored.
	ImagesOutputDirPath string
}

// NewWorkingDirectory initializes a new WorkingDirectory, creating any missing
// directories as needed.
func NewWorkingDirectory(workingDirPath string) (*WorkingDirectory, error) {
	if workingDirPath == "" {
		workingDirPath = defaultWorkingDirPath
	}
	err := os.MkdirAll(workingDirPath, fileutils.DefaultDirPermissions)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize working directory %q: %w", workingDirPath, err)
	}
	baseDirPath, err := filepath.Abs(workingDirPath)
	if err != nil {
		return nil, fmt.Errorf("failed to get absolute path of workingDirPath %q: %w", workingDirPath, err)
	}
	workingDir := &WorkingDirectory{
		BaseDirPath:                      baseDirPath,
		SdkDownloadsDirPath:              filepath.Join(baseDirPath, "downloads/sdk"),
		ImageBuilderDownloadsDirPath:     filepath.Join(baseDirPath, "downloads/image_builder"),
		SdkDirPath:                       filepath.Join(baseDirPath, "build/sdk"),
		ImageBuilderDirPath:              filepath.Join(baseDirPath, "build/image_builder"),
		ImageBuilderIncludedFilesDirPath: filepath.Join(baseDirPath, "build/image_builder_included_files"),
		PackagesOutputDirPath:            filepath.Join(baseDirPath, "output/packages"),
		ImagesOutputDirPath:              filepath.Join(baseDirPath, "output/images"),
	}
	dirPathsToCreate := []string{
		workingDir.SdkDownloadsDirPath,
		workingDir.ImageBuilderDownloadsDirPath,
		workingDir.SdkDirPath,
		workingDir.ImageBuilderDirPath,
		workingDir.ImageBuilderIncludedFilesDirPath,
		workingDir.PackagesOutputDirPath,
		workingDir.ImagesOutputDirPath,
	}
	for _, dirPath := range dirPathsToCreate {
		if err := os.MkdirAll(dirPath, fileutils.DefaultDirPermissions); err != nil {
			return nil, fmt.Errorf("failed to initialize directory %q: %w", dirPath, err)
		}
	}
	return workingDir, nil
}

// CleanIntermediaryFiles removes all files in the sdk and image builder
// directories.
func (wd *WorkingDirectory) CleanIntermediaryFiles() error {
	log.Logger.Println("Cleaning intermediary files")
	if err := wd.CleanSdk(); err != nil {
		return err
	}
	if err := wd.CleanImageBuilder(); err != nil {
		return err
	}
	return nil
}

// CleanSdk empties the WorkingDirectory.SdkDirPath directory.
func (wd *WorkingDirectory) CleanSdk() error {
	if err := fileutils.CleanDirectory(wd.SdkDirPath); err != nil {
		return fmt.Errorf("failed to clean directory %q: %w", wd.SdkDirPath, err)
	}
	return nil
}

// CleanImageBuilder empties the WorkingDirectory.ImageBuilderDirPath directory.
func (wd *WorkingDirectory) CleanImageBuilder() error {
	if err := fileutils.CleanDirectory(wd.ImageBuilderDirPath); err != nil {
		return fmt.Errorf("failed to clean directory %q: %w", wd.ImageBuilderDirPath, err)
	}
	return nil
}

// CleanAll removes all working directories and files by deleting the
// WorkingDirectory.BaseDirPath directory.
func (wd *WorkingDirectory) CleanAll() error {
	log.Logger.Printf("Removing working directory %q\n", wd.BaseDirPath)
	if err := os.RemoveAll(wd.BaseDirPath); err != nil {
		return fmt.Errorf("failed to remove working directory %q: %w", wd.BaseDirPath, err)
	}
	return nil
}

// SrcDirectory defines related source directories.
type SrcDirectory struct {
	// ChromiumosDirPath is the path to the root chromiumos source directory.
	ChromiumosDirPath string

	// CrosOpenWrtDirPath is the path to the project source directory root.
	CrosOpenWrtDirPath string

	// CustomPackagesDirPath is the path to the custom packages source directory.
	CustomPackagesDirPath string

	// IncludedImagesFilesDirPath is the path to the included image files
	// directory.
	IncludedImagesFilesDirPath string
}

// NewSrcDirectory creates a new SrcDirectory and validates that all required
// directories exist under chromiumosDirPath.
func NewSrcDirectory(chromiumosDirPath string) (*SrcDirectory, error) {
	chromiumosDirPathAbs, err := filepath.Abs(chromiumosDirPath)
	if err != nil {
		return nil, fmt.Errorf("failed to get absolute path of chromiumos dir %q: %w", chromiumosDirPath, err)
	}
	if _, err := os.Stat(chromiumosDirPathAbs); os.IsNotExist(err) {
		return nil, fmt.Errorf("%q does not exist: %w", chromiumosDirPathAbs, err)
	}
	crosOpenWrtDirPath := filepath.Join(chromiumosDirPathAbs, "src/platform/dev/contrib/cros_openwrt")
	srcDir := &SrcDirectory{
		ChromiumosDirPath:          chromiumosDirPathAbs,
		CrosOpenWrtDirPath:         crosOpenWrtDirPath,
		CustomPackagesDirPath:      filepath.Join(crosOpenWrtDirPath, "custom_packages"),
		IncludedImagesFilesDirPath: filepath.Join(crosOpenWrtDirPath, "included_image_files"),
	}
	if _, err := os.Stat(srcDir.CustomPackagesDirPath); os.IsNotExist(err) {
		return nil, fmt.Errorf("%q does not exist: %w", srcDir.CustomPackagesDirPath, err)
	}
	if _, err := os.Stat(srcDir.IncludedImagesFilesDirPath); os.IsNotExist(err) {
		return nil, fmt.Errorf("%q does not exist: %w", srcDir.IncludedImagesFilesDirPath, err)
	}
	return srcDir, nil
}
