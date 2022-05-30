// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// LaCrOSInstall state machine construction and helper

package lacrosservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/info"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"path"
	"regexp"
	"strconv"
	"strings"

	conf "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
)

var versionRegex = regexp.MustCompile(`^(\d+\.)(\d+\.)(\d+\.)(\d+)$`)

const crosComponentRootPath = "/home/chronos/cros-components"

// LaCrOSService inherits ServiceInterface
type LaCrOSService struct {
	connection      services.ServiceAdapterInterface
	imagePath       *conf.StoragePath
	metadata        *LaCrOSMetadata
	overrideVersion string
	componentPath   string
}

func NewLaCrOSService(dut *lab_api.Dut, dutClient api.DutServiceClient, req *api.InstallLacrosRequest) (LaCrOSService, error) {
	service := LaCrOSService{
		connection: services.NewServiceAdapter(dut, dutClient, false /*noReboot*/),
		imagePath:  req.LacrosImagePath,
	}

	metadata, err := service.ExtractLacrosMetadata(context.Background())
	if err != nil {
		return service, fmt.Errorf("could not extract metadata, %w", err)
	}

	service.metadata = metadata
	if req.OverrideVersion != "" {
		if !versionRegex.MatchString(req.OverrideVersion) {
			return service, fmt.Errorf("failed to parse version: %v", req.OverrideVersion)
		}
		service.overrideVersion = req.OverrideVersion
	}

	if req.OverrideInstallPath != "" {
		service.componentPath = req.OverrideInstallPath
	} else {
		service.componentPath = info.LaCrOSRootComponentPath
	}

	return service, nil
}

// NewLaCrOSServiceFromExistingConnection is equivalent to the above constructor,
// but recycles a ServiceAdapter. Generally useful for tests.
func NewLaCrOSServiceFromExistingConnection(conn services.ServiceAdapterInterface, imagePath *conf.StoragePath, metadata *LaCrOSMetadata, overrideVersion string, overrideInstallPath string) LaCrOSService {
	return LaCrOSService{
		connection:      conn,
		imagePath:       imagePath,
		metadata:        metadata,
		overrideVersion: overrideVersion,
		componentPath:   overrideInstallPath,
	}
}

// GetFirstState returns the first state of this state machine
func (c *LaCrOSService) GetFirstState() services.ServiceState {
	return LaCrOSInstallState{
		service: *c,
	}
}

// CleanupOnFailure is called if one of service's states failes to Execute() and
// should clean up the temporary files, and undo the execution, if feasible.
func (c *LaCrOSService) CleanupOnFailure(states []services.ServiceState, executionErr error) error {
	// TODO: evaluate whether cleanup is needed.
	return nil
}

/*
	The following consists of helper structs
*/
type LaCrOSMetadata struct {
	Content struct {
		Version string `json:"version"`
	} `json:"content"`
}

/*
	The following run specific commands related to LaCrOS installation.
*/

func (l *LaCrOSService) GetMetatadaPath() string {
	return path.Join(l.imagePath.GetPath(), "metadata.json")
}

func (l *LaCrOSService) GetCompressedImagePath() string {
	return path.Join(l.imagePath.GetPath(), "lacros_compressed.squash")
}

func (l *LaCrOSService) GetDeviceCompressedImagePath() string {
	return path.Join(l.imagePath.GetPath(), "lacros.squash")
}

func (l *LaCrOSService) GetComponentPath() string {
	return path.Join(l.componentPath, l.metadata.Content.Version)
}

func (l *LaCrOSService) GetLocalImagePath() string {
	return path.Join(l.GetComponentPath(), "image.squash")
}

func (l *LaCrOSService) GetHashTreePath() string {
	return path.Join(l.GetComponentPath(), "hashtree")
}

func (l *LaCrOSService) GetTablePath() string {
	return path.Join(l.GetComponentPath(), "table")
}

func (l *LaCrOSService) GetManifestPath() string {
	return path.Join(l.GetComponentPath(), "imageloader.json")
}

func (l *LaCrOSService) GetComponentManifestPath() string {
	return path.Join(l.GetComponentPath(), "manifest.json")
}

func (l *LaCrOSService) GetLatestVersionPath() string {
	return path.Join(info.LaCrOSRootComponentPath, "latest-version")
}

// extractLacrosMetadata will unmarshal the metadata.json in the GS path into the state.
func (l *LaCrOSService) ExtractLacrosMetadata(ctx context.Context) (*LaCrOSMetadata, error) {
	switch l.imagePath.HostType {
	case conf.StoragePath_GS:
		if err := l.connection.CopyData(ctx, l.GetMetatadaPath(), "/tmp/metadata.json"); err != nil {
			return nil, fmt.Errorf("failed to cache Lacros metadata.json, %w", err)
		}
	case conf.StoragePath_LOCAL:
		if _, err := l.connection.RunCmd(ctx, "cp", []string{l.GetMetatadaPath(), "/tmp/metadata.json"}); err != nil {
			return nil, fmt.Errorf("failed to copy Lacros metadata.json, %w", err)
		}
	default:
		return nil, fmt.Errorf("only GS and LOCAL copying are implemented")
	}
	metadataJSONStr, err := l.connection.RunCmd(ctx, "cat", []string{"/tmp/metadata.json"})
	if err != nil {
		return nil, fmt.Errorf("failed to read Lacros metadata.json, %w", err)
	}
	metadataJSON := LaCrOSMetadata{}
	if err := json.Unmarshal([]byte(metadataJSONStr), &metadataJSON); err != nil {
		return nil, fmt.Errorf("failed to unmarshal Lacros metadata.json, %w", err)
	}
	if l.overrideVersion != "" {
		metadataJSON.Content.Version = l.overrideVersion
	}
	return &metadataJSON, nil
}

// CopyImageToDUT copies the desired image to the DUT, passing through the caching layer.
func (l *LaCrOSService) CopyImageToDUT(ctx context.Context) error {
	if err := l.connection.CreateDirectories(ctx, []string{l.GetComponentPath()}); err != nil {
		return fmt.Errorf("failed to create directory, %w", err)
	}

	switch l.imagePath.HostType {
	case conf.StoragePath_GS:
		if err := l.connection.CopyData(ctx, l.GetCompressedImagePath(), l.GetLocalImagePath()); err != nil {
			return fmt.Errorf("failed to cache lacros compressed, %w", err)
		}
	case conf.StoragePath_LOCAL:
		if _, err := l.connection.RunCmd(ctx, "cp", []string{l.GetDeviceCompressedImagePath(), l.GetLocalImagePath()}); err != nil {
			return fmt.Errorf("failed to copy lacros compressed, %w", err)
		}
	default:
		return fmt.Errorf("only GS and LOCAL copying are implemented")
	}

	return nil
}

// RunVerity generates the verity (hashtree and table) from Lacros image.
func (l *LaCrOSService) RunVerity(ctx context.Context, payloadBlocks int) error {
	// Generate the verity (hashtree and table) from Lacros image.
	if _, err := l.connection.RunCmd(ctx, "verity", []string{
		"mode=create",
		"alg=sha256",
		fmt.Sprintf("payload=%s", l.GetLocalImagePath()),
		fmt.Sprintf("payload_blocks=%d", payloadBlocks),
		fmt.Sprintf("hashtree=%s", l.GetHashTreePath()),
		"salt=random",
		">",
		l.GetTablePath(),
	}); err != nil {
		return fmt.Errorf("failed to generate verity for Lacros image, %w", err)
	}
	return nil
}

// Append the hashtree (merkle tree) onto the end of the Lacros image.
func (l *LaCrOSService) AppendHashtree(ctx context.Context) error {
	if _, err := l.connection.RunCmd(ctx, "cat", []string{
		l.GetHashTreePath(),
		">>",
		l.GetLocalImagePath(),
	}); err != nil {
		return fmt.Errorf("failed to append hashtree to Lacros image, %w", err)
	}
	return nil
}

// AlignImageToPage will align the file to LacrosPageSize page alignment and return the number of page blocks.
func (l *LaCrOSService) AlignImageToPage(ctx context.Context) (int, error) {
	sizeStr, err := l.connection.RunCmd(ctx, "stat", []string{"-c%s", l.GetLocalImagePath()})
	if err != nil {
		return 0, fmt.Errorf("failed to get image size, %w", err)
	}
	size, err := strconv.Atoi(strings.TrimSpace(sizeStr))
	if err != nil {
		return 0, fmt.Errorf("failed to get image size as an integer, %w", err)
	}

	// Round up to the nearest LaCrOSPageSize block size.
	blocks := (size + info.LaCrOSPageSize - 1) / info.LaCrOSPageSize

	// Check if the Lacros image is LacrosPageSize  aligned, if not extend it to LacrosPageSize alignment.
	if size != blocks*info.LaCrOSPageSize {
		log.Printf("image %s isn't aligned to %d, so extending it", l.GetLocalImagePath(), info.LaCrOSPageSize)
		inputBlockCount := blocks*info.LaCrOSPageSize - size
		if _, err := l.connection.RunCmd(
			ctx,
			"dd",
			[]string{"if=/dev/zero",
				"bs=1",
				fmt.Sprintf("count=%d", inputBlockCount),
				fmt.Sprintf("seek=%d", size),
				fmt.Sprintf("of=%s", l.GetLocalImagePath()),
			}); err != nil {
			return 0, fmt.Errorf("failed to align image to %d, %w", info.LaCrOSPageSize, err)
		}
	}
	return blocks, nil
}

// getSHA256Sum will get the SHA256 sum of a file on the device.
func (l *LaCrOSService) getSHA256Sum(ctx context.Context, path string) (string, error) {
	hash, err := l.connection.RunCmd(ctx, "sha256sum", []string{
		path,
		"|",
		"cut", "-d' '", "-f1",
	})
	if err != nil {
		return "", fmt.Errorf("failed to get hash of %s, %w", path, err)
	}
	return strings.TrimSpace(hash), nil
}

// writeToFile takes a string and writes its contents to a file on a DUT.
func (l *LaCrOSService) writeToFile(ctx context.Context, data, outputPath string) error {
	if _, err := l.connection.RunCmd(ctx, "echo", []string{
		fmt.Sprintf("'%s'", data), ">", outputPath,
	}); err != nil {
		return fmt.Errorf("failed to write data to file, %w", err)
	}
	return nil
}

// writeManifest will create and write the Lacros component manifest out.
func (l *LaCrOSService) writeManifest(ctx context.Context) error {
	imageHash, err := l.getSHA256Sum(ctx, l.GetLocalImagePath())
	if err != nil {
		return fmt.Errorf("failed to get Lacros image hash, %w", err)
	}
	tableHash, err := l.getSHA256Sum(ctx, l.GetTablePath())
	if err != nil {
		return fmt.Errorf("failed to get Lacros table hash, %w", err)
	}
	lacrosManifestJSON, err := json.MarshalIndent(struct {
		ManifestVersion int    `json:"manifest-version"`
		FsType          string `json:"fs-type"`
		Version         string `json:"version"`
		ImageSha256Hash string `json:"image-sha256-hash"`
		TableSha256Hash string `json:"table-sha256-hash"`
	}{
		ManifestVersion: 1,
		FsType:          "squashfs",
		Version:         l.metadata.Content.Version,
		ImageSha256Hash: imageHash,
		TableSha256Hash: tableHash,
	}, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to Marshal Lacros manifest json, %w", err)
	}
	return l.writeToFile(ctx, string(lacrosManifestJSON), l.GetManifestPath())
}

// writeComponentManifest will create and write the Lacros component manifest out usable by component updater.
func (l *LaCrOSService) writeComponentManifest(ctx context.Context) error {
	lacrosComponentManifestJSON, err := json.MarshalIndent(struct {
		ManifestVersion int    `json:"manifest-version"`
		Name            string `json:"name"`
		Version         string `json:"version"`
		ImageName       string `json:"imageName"`
		Squash          bool   `json:"squash"`
		FsType          string `json:"fsType"`
		IsRemovable     bool   `json:"isRemovable"`
	}{
		ManifestVersion: 2,
		Name:            "lacros",
		Version:         l.metadata.Content.Version,
		ImageName:       "image.squash",
		Squash:          true,
		FsType:          "squashfs",
		IsRemovable:     false,
	}, "", "  ")
	if err != nil {
		return fmt.Errorf("writeComponentManifest: failed to Marshal Lacros manifest json, %w", err)
	}
	return l.writeToFile(ctx, string(lacrosComponentManifestJSON), l.GetComponentManifestPath())
}

// PublishVersion writes the Lacros version to the latest-version file.
func (l *LaCrOSService) PublishVersion(ctx context.Context) error {
	return l.writeToFile(ctx, l.metadata.Content.Version, l.GetLatestVersionPath())
}

// FixOwnership changes file mode and owner of provisioned files if the path is
// prefixed with the CrOS component path.
func (l *LaCrOSService) FixOwnership(ctx context.Context) error {
	if strings.HasPrefix(l.componentPath, crosComponentRootPath) {
		if _, err := l.connection.RunCmd(ctx, "chown", []string{"-R", "chronos:chronos", crosComponentRootPath}); err != nil {
			return fmt.Errorf("could not change component path ownership for %s, %s", crosComponentRootPath, err)
		}
		if _, err := l.connection.RunCmd(ctx, "chmod", []string{"-R", "0755", crosComponentRootPath}); err != nil {
			return fmt.Errorf("could not change component path permissions for %s, %s", crosComponentRootPath, err)

		}
	}
	return nil
}
