// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package openwrt

import (
	"context"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"chromiumos/platform/dev/contrib/cros_openwrt/image_builder/fileutils"
)

type ImageBuilderRunner struct {
	builderDirPath         string
	runMakeImageScriptPath string
	binDirPath             string
}

type MakeImageArgs struct {
	// Profile specifies the target image to build.
	Profile string

	// IncludePackages is a list of packages to embed into the image.
	IncludePackages []string

	// ExcludePackages is a list of packages to exclude from the image.
	ExcludePackages []string

	// Files is a path to a	directory with custom files to include in the image.
	Files string

	// ExtraImageName is added to the output image filename.
	ExtraImageName string

	// DisabledServices is a list of service names from /etc/init.d to disable.
	DisabledServices []string
}

func NewImageBuilderRunner(builderDirPath, runMakeImageScriptPath string) (*ImageBuilderRunner, error) {
	ib := &ImageBuilderRunner{
		builderDirPath:         builderDirPath,
		runMakeImageScriptPath: runMakeImageScriptPath,
		binDirPath:             path.Join(builderDirPath, "bin"),
	}
	if err := fileutils.AssertDirectoriesExist(ib.builderDirPath); err != nil {
		return nil, err
	}
	return ib, nil
}

// MakeImage runs "make image" in the image builder directory with imageArgs.
//
// The "make image" command is run through the run_make_image.sh bash script
// so that its arguments are passed correctly, as it relies on bash to pass
// them in a way that is not supported with golang's exec.
func (ib *ImageBuilderRunner) MakeImage(ctx context.Context, imageArgs *MakeImageArgs) error {
	// Clean local image output directory, if it exists.
	binDirExists, err := fileutils.DirectoryExists(ib.binDirPath)
	if err != nil {
		return err
	}
	if binDirExists {
		if err := fileutils.CleanDirectory(ib.binDirPath); err != nil {
			return err
		}
	}

	var runMakeImageArgs []string

	// BUILDER_DIR run script arg, where to run "make image".
	runMakeImageArgs = append(runMakeImageArgs, ib.builderDirPath)

	// PROFILE arg.
	if imageArgs.Profile == "" {
		return errors.New("target image profile is required")
	}
	runMakeImageArgs = append(runMakeImageArgs, imageArgs.Profile)

	// PACKAGES arg.
	packagesArg := imageArgs.IncludePackages
	for _, packageName := range imageArgs.ExcludePackages {
		packagesArg = append(packagesArg, "-"+packageName)
	}
	runMakeImageArgs = append(runMakeImageArgs, strings.Join(packagesArg, " "))

	// FILES arg.
	runMakeImageArgs = append(runMakeImageArgs, imageArgs.Files)

	// EXTRA_IMAGE_NAME arg.
	runMakeImageArgs = append(runMakeImageArgs, imageArgs.ExtraImageName)

	// DISABLED_SERVICES arg.
	runMakeImageArgs = append(runMakeImageArgs, strings.Join(imageArgs.DisabledServices, " "))

	cmd := exec.CommandContext(ctx, "bash", append([]string{ib.runMakeImageScriptPath}, runMakeImageArgs...)...)
	cmd.Dir = ib.builderDirPath
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to run image builder 'make image' with args %v: %w", runMakeImageArgs, err)
	}
	return nil
}

// AvailableProfiles runs "make info" to retrieve available image profiles this
// image builder supports as a map of profile to its description.
func (ib *ImageBuilderRunner) AvailableProfiles(ctx context.Context) (map[string]string, error) {
	// Run "make info" and collect output.
	cmd := exec.CommandContext(ctx, "make", "info")
	cmd.Dir = ib.builderDirPath
	cmd.Stderr = os.Stderr
	stdout, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("failed to run image builder make info: %w", err)
	}
	makeInfoOutput := string(stdout)

	// Parse out available profiles and device names.
	availProfilesLine := "Available Profiles:"
	profilesStartIndex := strings.Index(makeInfoOutput, availProfilesLine) + len(availProfilesLine)
	if profilesStartIndex >= len(makeInfoOutput) {
		return nil, fmt.Errorf("failed to parse image builder make info output for profiles:\n%s", makeInfoOutput)
	}
	availProfilesOutput := makeInfoOutput[profilesStartIndex:]
	profileAndDescriptionRegex := regexp.MustCompile(`\n([^:]+):\n\s+([^\n]+)\n\s+Packages:`)
	matches := profileAndDescriptionRegex.FindAllStringSubmatch(availProfilesOutput, -1)
	if matches == nil {
		return nil, fmt.Errorf("found no available profiles from image builder make info output:\n%s", availProfilesOutput[0:1000])
	}
	availProfilesToDescription := make(map[string]string)
	for _, profileMatch := range matches {
		availProfilesToDescription[strings.TrimSpace(profileMatch[1])] = strings.TrimSpace(profileMatch[2])
	}
	return availProfilesToDescription, nil
}

// ExportBuiltImage exports built OpenWrt OS image built
func (ib *ImageBuilderRunner) ExportBuiltImage(ctx context.Context, dstDir string) (string, error) {
	binDirExists, err := fileutils.DirectoryExists(ib.binDirPath)
	if err != nil {
		return "", err
	}
	if !binDirExists {
		return "", fmt.Errorf("image builder bin directory not found at %q")
	}

	// Find directory of the image (i.e. the first directory with a *.manifest file).
	var localImageDir string
	var localImageName string
	const manifestFileSuffix = ".manifest"
	if err := filepath.Walk(ib.binDirPath, func(filePath string, info fs.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.Mode().IsRegular() && strings.HasSuffix(info.Name(), manifestFileSuffix) {
			// Found manifest file.
			localImageDir = path.Dir(filePath)
			localImageName = strings.TrimSuffix(info.Name(), manifestFileSuffix)
		}
		return nil
	}); err != nil {
		return "", err
	}
	if localImageDir == "" || localImageName == "" {
		return "", fmt.Errorf("failed to find local built image in image builder bin dir %q", ib.binDirPath)
	}

	// Build the export directory subdir for this image.
	timestamp := fileutils.BuildTimestampForFilePath(time.Now())
	exportImageDir := path.Join(dstDir, fmt.Sprintf("%s_%s", localImageName, timestamp))
	if err := os.MkdirAll(exportImageDir, fileutils.DefaultDirPermissions); err != nil {
		return "", fmt.Errorf("failed to build image export dir %q: %w", exportImageDir, err)
	}

	// Copy image files to export dir (for local use).
	if err := fileutils.CopyFilesInDirToDir(ctx, localImageDir, exportImageDir); err != nil {
		return "", err
	}

	// Create and export an archive of the image (for distribution).
	archivePath := path.Join(exportImageDir, path.Base(exportImageDir)+".tar.xz")
	if err := fileutils.PackageTarXz(ctx, localImageDir, archivePath); err != nil {
		return "", err
	}

	return exportImageDir, nil
}
