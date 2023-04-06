// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"errors"
	"fmt"
	"os/user"
	"path"

	"chromiumos/platform/dev/contrib/cros_openwrt/image_builder/openwrt"
	"github.com/spf13/cobra"
)

var (
	rootCmd = &cobra.Command{
		Use:     "cros_openwrt_image_builder",
		Version: "1.0.4",
		Short:   "Utility for building custom OpenWrt OS images with custom compiled packages",
		PersistentPreRunE: func(cmd *cobra.Command, args []string) error {
			if useExisting {
				useExistingSdk = true
				useExistingImageBuilder = true
			}
			if autoURL != "" && (!useExistingSdk && !useExistingImageBuilder) {
				// Resolve URLs.
				resolvedSdkURL, resolvedImageBuilderURL, err := openwrt.AutoResolveDownloadURLs(cmd.Context(), autoURL)
				if err != nil {
					return fmt.Errorf("failed to auto resolve download URLs from %q: %w", autoURL, err)
				}
				if sdkURL == "" {
					sdkURL = resolvedSdkURL
				}
				if imageBuilderURL == "" {
					imageBuilderURL = resolvedImageBuilderURL
				}

				// Prompt user for verification.
				promptMsg := fmt.Sprintf(
					"Resolved sdk download URL: %s\nResolved image builder download URL: %s\n\nUse these download URLs?",
					sdkURL,
					imageBuilderURL,
				)
				answer, err := promptYesNo(cmd.Context(), promptMsg, true)
				if err != nil {
					return err
				}
				if !answer {
					return errors.New("aborted by user")
				}
			}
			return nil
		},
	}

	// Persistent CLI Flags.
	chromiumosDirPath            string
	workingDirPath               string
	sdkURL                       string
	imageBuilderURL              string
	autoURL                      string
	useExistingSdk               bool
	useExistingImageBuilder      bool
	useExisting                  bool
	imageProfile                 string
	imageDisabledServices        []string
	includedCustomPackages       []string
	includedOfficialPackages     []string
	imagePackageExcludes         []string
	sdkSourcePackageMakefileDirs []string
	extraImageName               string
	autoRetrySdkCompile          bool
	sdkCompileMaxCPUs            int
	sdkConfigOverrides           map[string]string
)

func init() {
	usr, err := user.Current()
	if err != nil {
		panic("Failed to get user home directory path")
	}

	// Source options.
	rootCmd.PersistentFlags().StringVar(
		&chromiumosDirPath,
		"chromiumos_src_dir",
		path.Join(usr.HomeDir, "chromiumos"),
		"Path to local chromiumos source directory.",
	)
	rootCmd.PersistentFlags().StringVar(
		&workingDirPath,
		"working_dir",
		"/tmp/cros_openwrt",
		"Path to working directory to store downloads, sdk, image builder, and built packages and images.",
	)
	rootCmd.PersistentFlags().StringVar(
		&sdkURL,
		"sdk_url",
		"",
		"URL to download the sdk archive from. Leave unset to use the last downloaded sdk.",
	)
	rootCmd.PersistentFlags().StringVar(
		&imageBuilderURL,
		"image_builder_url",
		"",
		"URL to download the image builder archive from. Leave unset to use the last downloaded image builder.",
	)
	rootCmd.PersistentFlags().StringVar(
		&autoURL,
		"auto_url",
		"",
		"Download URL to use to auto resolve unset --sdk_url and --image_builder_url values from.",
	)
	rootCmd.PersistentFlags().BoolVar(
		&useExistingSdk,
		"use_existing_sdk",
		false,
		"Use sdk in working directory as-is (must exist).",
	)
	rootCmd.PersistentFlags().BoolVar(
		&useExistingSdk,
		"use_existing_image_builder",
		false,
		"Use image builder in working directory as-is (must exist).",
	)
	rootCmd.PersistentFlags().BoolVar(
		&useExisting,
		"use_existing",
		false,
		"Shortcut to set both --use_existing_sdk and --use_existing_image_builder.",
	)

	// Optimization options.
	rootCmd.PersistentFlags().BoolVar(
		&autoRetrySdkCompile,
		"disable_auto_sdk_compile_retry",
		true,
		"Include to disable the default behavior of retrying the compilation of custom packages once if the first attempt fails.",
	)
	rootCmd.PersistentFlags().IntVar(
		&sdkCompileMaxCPUs,
		"sdk_compile_max_cpus",
		-1,
		"The maximum number of CPUs to use for custom package compilation. Values less than 1 indicate that all available CPUs may be used.",
	)

	// OpenWrt OS customization options.
	rootCmd.PersistentFlags().StringVar(
		&extraImageName,
		"extra_image_name",
		"",
		"A custom name to add to the image, added as a suffix to existing names.",
	)
	rootCmd.PersistentFlags().StringVar(
		&imageProfile,
		"image_profile",
		"",
		"The profile to use with the image builder when making images. Leave unset to prompt for selection based off of available profiles.",
	)
	rootCmd.PersistentFlags().StringToStringVar(
		&sdkConfigOverrides,
		"sdk_config",
		map[string]string{
			"CONFIG_WPA_MBO_SUPPORT":     "y",
			"CONFIG_WPA_ENABLE_WEP":      "y",
			"CONFIG_DRIVER_11N_SUPPORT":  "y",
			"CONFIG_DRIVER_11AC_SUPPORT": "y",
			"CONFIG_DRIVER_11AX_SUPPORT": "y",
		},
		"Config options to set for the sdk when compiling custom packages.",
	)
	rootCmd.PersistentFlags().StringArrayVar(
		&sdkSourcePackageMakefileDirs,
		"sdk_make",
		[]string{
			// Builds the cros-send-management-frame package.
			"cros-send-management-frame",

			// Builds hostapd*, wpa-supplicant*, wpad*, and eapol-test* packages.
			"feeds/base/hostapd",
		},
		"The sdk package makefile paths to use to compile custom IPKs. Making a package with the sdk will build all the IPKs that package depends upon, but only need to be included if they are expected to differ from official versions.",
	)
	rootCmd.PersistentFlags().StringArrayVar(
		&imageDisabledServices,
		"disable_service",
		[]string{
			"wpad",
			"dnsmasq",
		},
		"Services to disable in the built image.",
	)
	rootCmd.PersistentFlags().StringArrayVar(
		&includedCustomPackages,
		"include_custom_package",
		[]string{
			"cros-send-management-frame",
			"hostapd-common",
			"hostapd-utils",
			"wpad-openssl",
			"wpa-cli",
		},
		"Names of packages that should be included in built images that are built using a local sdk and included in the image builder as custom IPKs. Only custom packages in this list are saved from sdk package compilation.",
	)
	rootCmd.PersistentFlags().StringArrayVar(
		&includedOfficialPackages,
		"include_official_package",
		[]string{
			"iputils-ping",
			"iputils-arping",
			"kmod-veth",
			"tcpdump",
			"procps-ng-pkill",
			"netperf",
			"iperf",
			"sudo",
		},
		"Names of packages that should be included in built images that are downloaded from official OpenWrt repositories.",
	)
	rootCmd.PersistentFlags().StringArrayVar(
		&imagePackageExcludes,
		"exclude_package",
		[]string{
			// Exclude other versions of packages built by feeds/base/hostapd not being
			// used or that are redundant given those in IncludedCustomPackages.
			"hostapd",
			"hostapd-basic",
			"hostapd-basic-openssl",
			"hostapd-basic-wolfssl",
			"hostapd-mini",
			"hostapd-openssl",
			"hostapd-wolfssl",
			"wpad",
			"wpad-mesh-openssl",
			"wpad-mesh-wolfssl",
			"wpad-basic",
			"wpad-basic-openssl",
			"wpad-basic-wolfssl",
			"wpad-mini",
			"wpad-wolfssl",
			"wpa-supplicant",
			"wpa-supplicant-mesh-openssl",
			"wpa-supplicant-mesh-wolfssl",
			"wpa-supplicant-basic",
			"wpa-supplicant-mini",
			"wpa-supplicant-openssl",
			"wpa-supplicant-p2p",
			"eapol-test",
			"eapol-test-openssl",
			"eapol-test-wolfssl",
		},
		"Packages to exclude from the built image.",
	)
}
