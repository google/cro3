// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path"
	"sort"
	"strings"
	"time"

	"chromiumos/platform/dev/contrib/cros_openwrt/image_builder/dirs"
	"chromiumos/platform/dev/contrib/cros_openwrt/image_builder/fileutils"
	"chromiumos/platform/dev/contrib/cros_openwrt/image_builder/log"
	"chromiumos/platform/dev/contrib/cros_openwrt/image_builder/openwrt"
)

// CrosOpenWrtImageBuilder is a utility that can preform different steps related
// to building OpenWrt OS images customized for ChromeOS testing.
type CrosOpenWrtImageBuilder struct {
	src     *dirs.SrcDirectory
	wd      *dirs.WorkingDirectory
	sdk     *openwrt.SdkRunner
	builder *openwrt.ImageBuilderRunner
}

// NewCrosOpenWrtImageBuilder initializes a CrosOpenWrtImageBuilder and prepares
// its source and working directories for use.
func NewCrosOpenWrtImageBuilder() (*CrosOpenWrtImageBuilder, error) {
	ib := &CrosOpenWrtImageBuilder{}

	// Init src dir.
	src, err := dirs.NewSrcDirectory(chromiumosDirPath)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize src directory using chromiumos dir %q: %w", chromiumosDirPath, err)
	}
	ib.src = src

	// Init and clean working dir.
	wd, err := dirs.NewWorkingDirectory(workingDirPath)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize working directory at %q: %w", workingDirPath, err)
	}
	ib.wd = wd

	return ib, nil
}

func (ib *CrosOpenWrtImageBuilder) prepareSdk(ctx context.Context) error {
	log.Logger.Println("Preparing OpenWrt SDK for packaging")

	if useExistingSdk {
		log.Logger.Printf("Using existing sdk at %q\n", ib.wd.SdkDirPath)
	} else {
		// Clean old sdk copy.
		if err := ib.wd.CleanSdk(); err != nil {
			return nil
		}

		// Get sdk archive.
		var sdkArchivePath string
		var err error
		if sdkURL == "" {
			log.Logger.Println("No OpenWrt SDK archive download url specified, checking for previously download archive")
			sdkArchivePath, err = fileutils.GetLatestFilePathInDir(ib.wd.SdkDownloadsDirPath)
			if err != nil {
				return fmt.Errorf("failed to get latest sdk archive in download directory %q (Specify a new download URL with --sdk_url): %w", ib.wd.SdkDownloadsDirPath, err)
			}
		} else {
			log.Logger.Printf("Downloading OpenWrt SDK archive from %q\n", sdkURL)
			sdkArchivePath, err = fileutils.DownloadFileFromURL(ctx, sdkURL, ib.wd.SdkDownloadsDirPath)
			if err != nil {
				return fmt.Errorf("failed to download sdk archive from %q: %w", sdkURL, err)
			}
		}
		log.Logger.Printf("Using OpenWrt SDK archive at %q\n", sdkArchivePath)

		// Unpack sdk archive.
		log.Logger.Printf("Unpacking OpenWrt SDK archive to %q\n", ib.wd.SdkDirPath)
		if err := fileutils.UnpackTarXz(ctx, sdkArchivePath, ib.wd.SdkDirPath); err != nil {
			return err
		}
	}

	// Init sdk runner.
	log.Logger.Println("Initializing OpenWrt SDK runner")
	var err error
	ib.sdk, err = openwrt.NewSdkRunner(ib.wd.SdkDirPath)
	if err != nil {
		return fmt.Errorf("failed to initialize new sdk runner for sdk at %q: %w", ib.wd.SdkDirPath, err)
	}

	log.Logger.Println("Successfully prepared OpenWrt SDK for packaging")
	return nil
}

func (ib *CrosOpenWrtImageBuilder) prepareBuilder(ctx context.Context) error {
	log.Logger.Println("Preparing OpenWrt image builder")

	if useExistingImageBuilder {
		log.Logger.Printf("Using existing image builder at %q\n", ib.wd.ImageBuilderDirPath)
	} else {
		// Get builder archive.
		var builderArchivePath string
		var err error
		if imageBuilderURL == "" {
			log.Logger.Println("No OpenWrt image builder archive download url specified, checking for previously download archive")
			builderArchivePath, err = fileutils.GetLatestFilePathInDir(ib.wd.ImageBuilderDownloadsDirPath)
			if err != nil {
				return fmt.Errorf("failed to get latest image builder archive in download directory %q (Specify a new download URL with --image_builder_url): %w", ib.wd.ImageBuilderDownloadsDirPath, err)
			}
		} else {
			log.Logger.Printf("Downloading OpenWrt image builder archive from %q\n", imageBuilderURL)
			builderArchivePath, err = fileutils.DownloadFileFromURL(ctx, imageBuilderURL, ib.wd.ImageBuilderDownloadsDirPath)
			if err != nil {
				return fmt.Errorf("failed to download image builder archive from %q: %w", imageBuilderURL, err)
			}
		}
		log.Logger.Printf("Using OpenWrt image builder archive at %q\n", builderArchivePath)

		// Unpack builder archive.
		log.Logger.Printf("Unpacking OpenWrt image builder archive to %q\n", ib.wd.ImageBuilderDirPath)
		if err := fileutils.UnpackTarXz(ctx, builderArchivePath, ib.wd.ImageBuilderDirPath); err != nil {
			return fmt.Errorf("failed to unpack image builder archive from %q to %q: %w", builderArchivePath, ib.wd.ImageBuilderDirPath, err)
		}
	}

	// Copy custom-built IPKs to builder.
	builderPackagesDir := path.Join(ib.wd.ImageBuilderDirPath, "packages")
	if err := fileutils.CleanDirectory(builderPackagesDir); err != nil {
		return err
	}
	if err := fileutils.CopyFilesInDirToDir(ctx, ib.wd.PackagesOutputDirPath, builderPackagesDir); err != nil {
		return err
	}

	// Copy custom files from src to working.
	if err := fileutils.CleanDirectory(ib.wd.ImageBuilderIncludedFilesDirPath); err != nil {
		return err
	}
	if err := fileutils.CopyFilesInDirToDir(ctx, ib.src.IncludedImagesFilesDirPath, ib.wd.ImageBuilderIncludedFilesDirPath); err != nil {
		return err
	}

	// Copy the shared test key to included files as an authorized key so that it
	// may be used for ssh access to the router.
	dropbearDirPath := path.Join(ib.wd.ImageBuilderIncludedFilesDirPath, "etc/dropbear")
	if err := os.MkdirAll(dropbearDirPath, fileutils.DefaultDirPermissions); err != nil {
		return fmt.Errorf("failed to make dir %q: %w", dropbearDirPath)
	}
	crosPubKeyPath := path.Join(ib.src.ChromiumosDirPath, "chromeos-admin/puppet/modules/profiles/files/user-common/ssh/testing_rsa.pub")
	if err := fileutils.CopyFile(ctx, crosPubKeyPath, path.Join(dropbearDirPath, "authorized_keys")); err != nil {
		return err
	}

	// Resolve make image run script path.
	runMakeImageScriptPath := path.Join(ib.src.CrosOpenWrtDirPath, "image_builder/run_make_image.sh")

	// Init builder runner.
	log.Logger.Println("Initializing OpenWrt image builder runner")
	var err error
	ib.builder, err = openwrt.NewImageBuilderRunner(ib.wd.ImageBuilderDirPath, runMakeImageScriptPath)
	if err != nil {
		return fmt.Errorf("failed to initialize new image builder runner for image builder at %q: %w", ib.wd.ImageBuilderDirPath, err)
	}

	log.Logger.Println("Successfully prepared OpenWrt image builder")
	return nil
}

// CompileCustomPackages uses the OpenWrt sdk to compile custom/customized
// OpenWrt packages that may be installed on OpenWrt systems/images.
//
// Note: This also results in all the dependencies of the custom packages to be
// compiled as well, but only specifically chosen IPKs are saved for image
// building.
//
// Compiled custom package IPKs are saved to
// dirs.WorkingDirectory.PackagesOutputDirPath.
func (ib *CrosOpenWrtImageBuilder) CompileCustomPackages(ctx context.Context) error {
	if err := ib.prepareSdk(ctx); err != nil {
		return fmt.Errorf("failed to prepare sdk: %w", err)
	}

	log.Logger.Printf("Importing custom package sources from %q\n", ib.src.CustomPackagesDirPath)
	if err := ib.sdk.ImportCustomPackageSources(ctx, ib.src.CustomPackagesDirPath); err != nil {
		return err
	}

	log.Logger.Println("Compiling custom packages and their dependencies")
	if err := ib.sdk.CompileCustomPackages(ctx, sdkConfigOverrides, sdkSourcePackageMakefileDirs, autoRetrySdkCompile, sdkCompileMaxCPUs); err != nil {
		return fmt.Errorf("failed to compile custom packages with sdk: %w", err)
	}

	log.Logger.Printf("Exporting compiled custom package IPKs to %q\n", ib.wd.PackagesOutputDirPath)
	if err := ib.sdk.ExportCompiledCustomPackageIPKs(ctx, includedCustomPackages, ib.wd.PackagesOutputDirPath); err != nil {
		return fmt.Errorf("failed to export built custom package IPKs from sdk to %q: %w", ib.wd.PackagesOutputDirPath, err)
	}
	return nil
}

// BuildCustomChromeOSTestImage builds an OpenWrt OS image using the OpenWrt
// image builder that includes customizations for ChromeOS test APs.
//
// These customizations include:
//   - Inclusion of custom-built packages.
//   - Inclusion/exclusion of specific official packages.
//   - Inclusion of custom image files.
//   - A customized image name.
//   - The disabling of some core OpenWrt services that are not needed.
//
// This does not compile custom packages, it just uses precompiled package
// IPKs saved to dirs.WorkingDirectory.PackagesOutputDirPath as IPK overrides
// for packages and then makes adjustments to the package list for the images.
// If an included custom package IPK is provided, the image builder will use
// that IPK over an official IPK for with the same package name, allowing for
// overriding official package builds with customized versions. To compile
// custom packages, call CompileCustomPackages first in either this run or in
// a previous run.
//
// Built images are saved to dirs.WorkingDirectory.ImagesOutputDirPath.
func (ib *CrosOpenWrtImageBuilder) BuildCustomChromeOSTestImage(ctx context.Context) error {
	if err := ib.prepareBuilder(ctx); err != nil {
		return fmt.Errorf("failed to prepare builder: %w", err)
	}

	// Prepare make image args.
	log.Logger.Printf("Preparing image builder arguments")
	makeImageArgs := &openwrt.MakeImageArgs{
		Profile:          imageProfile,
		IncludePackages:  append(includedCustomPackages, includedOfficialPackages...),
		ExcludePackages:  imagePackageExcludes,
		Files:            ib.wd.ImageBuilderIncludedFilesDirPath,
		DisabledServices: imageDisabledServices,
		ExtraImageName:   "cros-" + rootCmd.Version,
	}
	if extraImageName != "" {
		makeImageArgs.ExtraImageName += "-" + extraImageName
	}
	if makeImageArgs.Profile == "" {
		log.Logger.Println("Image builder profile not specified with --image_profile, prompting user for selection")
		var err error
		makeImageArgs.Profile, err = ib.promptForImageProfile(ctx)
		if err != nil {
			return fmt.Errorf("failed to prompt user for image profile: %w", err)
		}
	}

	// Prepare a build summary and add to included files.
	log.Logger.Println("Preparing image build summary")
	buildSummary, err := ib.prepareBuildSummaryJSON(ctx, makeImageArgs)
	if err != nil {
		return fmt.Errorf("failed to prepare build summary: %w", err)
	}
	relativeImageBuildSummaryFilePath := "etc/cros/build_info.json"
	log.Logger.Printf("Image build summary (available on image install at \"/%s\":\n%s\n", relativeImageBuildSummaryFilePath, buildSummary)
	if err := fileutils.WriteStringToFile(ctx, buildSummary, path.Join(ib.wd.ImageBuilderIncludedFilesDirPath, relativeImageBuildSummaryFilePath)); err != nil {
		return fmt.Errorf("failed to save build build summary in included image files: %w", err)
	}

	// Make image.
	log.Logger.Println("Making image")
	err = ib.builder.MakeImage(ctx, makeImageArgs)
	if err != nil {
		return fmt.Errorf("failed to make image: %w", err)
	}

	// Export image.
	log.Logger.Println("Exporting built image")
	imageDirPath, err := ib.builder.ExportBuiltImage(ctx, ib.wd.ImagesOutputDirPath)
	if err != nil {
		return fmt.Errorf("failed to export built image: %w", err)
	}
	log.Logger.Printf("New OpenWrt OS image available at file://%s\n", imageDirPath)

	return nil
}

func (ib *CrosOpenWrtImageBuilder) promptForImageProfile(ctx context.Context) (string, error) {
	// Collect available profiles and sort by profile name.
	log.Logger.Println("Retrieving available profiles for this image builder")
	availProfiles, err := ib.builder.AvailableProfiles(ctx)
	if err != nil {
		return "", fmt.Errorf("failed to retrieve available profiles: %w", err)
	}
	var availProfileNamesSorted []string
	for name, _ := range availProfiles {
		availProfileNamesSorted = append(availProfileNamesSorted, name)
	}
	sort.Strings(availProfileNamesSorted)

	// Prompt selection from user until a valid answer is provided or the user
	// aborts. Options are only printed once.
	log.Logger.Printf("Prompting user to choose from one of the %d available image builder profiles\n", len(availProfiles))
	var selectedProfile string
	promptMsg := "\nAvailable image builder profiles:\n\n"
	promptMsg += fmt.Sprintf("%-30s  %-30s\n\n", "PROFILE NAME", "DEVICE DESCRIPTION")
	for _, name := range availProfileNamesSorted {
		description := availProfiles[name]
		promptMsg += fmt.Sprintf("%-30s  %-30s\n", name, description)
	}
	promptMsg += "\nPlease choose from one of the above available image builder profiles.\n"
	fmt.Print(promptMsg)
	for true {
		selectedProfile, err = contextualPrompt(ctx, "Profile: ")
		if err != nil {
			return "", err
		}
		selectedProfile = strings.TrimSpace(selectedProfile)

		if _, ok := availProfiles[selectedProfile]; !ok {
			fmt.Printf("Invalid profile %q\n", selectedProfile)
		} else {
			break
		}
	}
	log.Logger.Printf("Selected image builder profile %q for device %q\n", selectedProfile, availProfiles[selectedProfile])
	return selectedProfile, nil
}

func (ib *CrosOpenWrtImageBuilder) prepareBuildSummaryJSON(ctx context.Context, makeImageArgs *openwrt.MakeImageArgs) (string, error) {
	summaryStats := make(map[string]interface{})

	// Basic stats.
	summaryStats["EXTRA_IMAGE_NAME"] = makeImageArgs.ExtraImageName
	summaryStats["IMAGE_BUILDER_PROFILE"] = makeImageArgs.Profile
	summaryStats["INCLUDE_PACKAGES"] = makeImageArgs.IncludePackages
	summaryStats["EXCLUDED_PACKAGES"] = makeImageArgs.ExcludePackages
	summaryStats["DISABLED_SERVICES"] = makeImageArgs.DisabledServices
	summaryStats["CROS_IMAGE_BUILDER_VERSION"] = rootCmd.Version
	summaryStats["BUILD_DATETIME"] = time.Now().Format(time.RFC3339)

	// Packages customizations.
	packagesChecksums, err := fileutils.CollectFileChecksums(ctx, path.Join(ib.wd.ImageBuilderDirPath, "packages"))
	if err != nil {
		return "", err
	}
	summaryStats["CUSTOM_PACKAGES"] = packagesChecksums

	// File customizations.
	includedImageFileChecksums, err := fileutils.CollectFileChecksums(ctx, makeImageArgs.Files)
	if err != nil {
		return "", err
	}
	summaryStats["CUSTOM_INCLUDED_FILES"] = includedImageFileChecksums

	// Return as pretty marshalled JSON object to allow for easy script parsing
	// and human reading.
	summaryJson, err := json.MarshalIndent(summaryStats, "", "  ")
	if err != nil {
		return "", fmt.Errorf("failed to marshal build summary stats to json: %w", err)
	}
	return string(summaryJson) + "\n", nil
}
