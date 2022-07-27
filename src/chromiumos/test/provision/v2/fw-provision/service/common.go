// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package firmwareservice

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"context"
	"fmt"
	"log"
	"path"
	"path/filepath"
	"strings"
)

const FirmwarePathTmp = "/tmp/fw-provisioning-service/"
const CurlWithRetriesArgsFW = "-S -s -v -# -C - --retry 3 --retry-delay 60"

// ImageArchiveMetadata will be the value of the map in which the key is the
// gsPath, so we can avoid downloading/reprocessing same archives.
type ImageArchiveMetadata struct {
	ArchivePath string
	ArchiveDir  string
	ListOfFiles map[string]struct{}
}

func MakeImageArchiveMetadata(archivePath string, archiveDir string, listOfFiles []string) *ImageArchiveMetadata {
	m := &ImageArchiveMetadata{ArchivePath: archivePath, ArchiveDir: archiveDir, ListOfFiles: make(map[string]struct{})}
	for _, f := range listOfFiles {
		m.ListOfFiles[f] = struct{}{}
	}
	return m
}

func (m *ImageArchiveMetadata) IncludesFile(filename string) bool {
	_, isPresent := m.ListOfFiles[filename]
	return isPresent
}

// extractFileFromImage extracts a single file from an archive to a provided folder.
// Returns (extractedFilePath, error)
func extractFileFromImage(ctx context.Context, fileInArchive string, imageMetadata ImageArchiveMetadata, s common_utils.ServiceAdapterInterface) (string, error) {
	// tar throws a strange "Cannot open: Read-only file system" error, if
	// --directory is used. cd to the directory instead.
	out, err := s.RunCmd(ctx, "cd", []string{imageMetadata.ArchiveDir, "&&", "tar", "-xvf", imageMetadata.ArchivePath, fileInArchive})
	if err != nil {
		err = fmt.Errorf("failed to extract file from image: %w\nOutput:\n%v", err, out)
	}
	return path.Join(imageMetadata.ArchiveDir, fileInArchive), err
}

// downloadAndProcessArchive downloads image from gsPath onto whatever device
// is connected to |s|.
// Returns ImageArchiveMetadata with metadata about the archive.
func downloadAndProcessArchive(ctx context.Context, s common_utils.ServiceAdapterInterface, gsPath string) (*ImageArchiveMetadata, error) {
	// Infer names for the local files and folders from basename of gsPath.
	archiveFilename := filepath.Base(gsPath)

	// Try to get a descriptive name for the temporary folder.
	archiveSubfolder := archiveFilename
	// The base filename of gspath will vary depending on the bucket:
	//  chromeos-releases: gs://.../ChromeOS-firmware-R98-14382.0.0-hatch.tar.bz2
	//  chromeos-image-archive: gs://.../R98-14382.0.0/firmware_from_source.tar.bz2
	// In the latter case, basename of gsPath will be "firmware_from_source.tar.bz2",
	// so use second-to-last directory in the gsPath (R98-14382.0.0).
	if strings.HasPrefix(archiveSubfolder, "firmware_from_source") {
		splitGsPath := strings.Split(gsPath, "/")
		nameIdx := len(splitGsPath) - 2
		if nameIdx < 0 {
			nameIdx = 0
		}
		archiveSubfolder = splitGsPath[nameIdx]
	}

	// Use mktemp to safely create a unique temp directory.
	archiveDir, err := s.RunCmd(ctx, "mktemp", []string{"-d", "--tmpdir", "fw-provision.XXXXXXXXX." + archiveSubfolder})
	if err != nil {
		return nil, fmt.Errorf("remote mktemp failed: %w", err)
	}
	archiveDir = strings.Trim(archiveDir, "\n")

	// Download the archive and defer its deletion.
	archivePath := path.Join(archiveDir, archiveFilename)

	if err := s.CopyData(ctx, gsPath, archivePath); err != nil {
		s.DeleteDirectory(ctx, archiveDir)
		return nil, fmt.Errorf("remote CopyData() failed: %w", err)
	}

	listOfFiles, err := listFilesInArchive(ctx, archivePath, s)
	if err != nil {
		s.DeleteDirectory(ctx, archiveDir)
		return nil, fmt.Errorf("failed to list archive contents: %w", err)
	}

	metadata := MakeImageArchiveMetadata(archivePath, archiveDir, listOfFiles)
	return metadata, nil
}

// GetFlashECScript finds flash_ec script locally and returns path to it.
// If flash_ec is not found, download the latest version with git to |prefix|,
// and return path to downloaded flash_ec.
func GetFlashECScript(ctx context.Context, s common_utils.ServiceAdapterInterface, prefix string) (string, error) {
	// flash_ec within checkout will have access to the dependencies/config files
	preferredFlashEC := "~/chromiumos/src/platform/ec/util/flash_ec"
	if preferredExists, err := s.PathExists(ctx, preferredFlashEC); preferredExists && err == nil {
		return preferredFlashEC, nil
	}

	// find any other flash_ec
	flashEC, err := s.RunCmd(ctx, "which", []string{"flash_ec"})
	if len(flashEC) > 0 && err == nil {
		// `which` found the script
		return strings.TrimRight(flashEC, "\n"), nil
	}

	// donwload the platform/ec repo to get the flash_ec script
	log.Println("flash_ec script not found, downloading")
	_, err = s.RunCmd(ctx, "", []string{"cd " + prefix + ";", "git", "clone",
		"https://chromium.googlesource.com/chromiumos/platform/ec", "ec-repo"})
	if err != nil {
		return "", fmt.Errorf("falied to checkout platform/ec repo: %w", err)
	}

	// TODO: mv ec-repo to some location and try it before downloading.

	return path.Join(prefix, "ec-repo", "util", "flash_ec"), nil
}

func listFilesInArchive(ctx context.Context, archivePath string, s common_utils.ServiceAdapterInterface) ([]string, error) {
	out, err := s.RunCmd(ctx, "tar", []string{"-tf", archivePath})
	if err != nil {
		return nil, err
	}

	return strings.Split(out, "\n"), nil
}

// PickAndExtractMainImage uses provided list of |filesInArchive| to pick a main
// image to use, extracts only it, and returns a path to extracted image.
// board and model(aka variant) are optional.
func PickAndExtractMainImage(ctx context.Context, s common_utils.ServiceAdapterInterface, imageMetadata ImageArchiveMetadata, board, model string) (string, error) {
	candidates := []string{}
	if len(model) > 0 {
		filePath := path.Join(fmt.Sprintf("image-%v.bin", model))
		candidates = append(candidates, filePath)
	}
	if len(board) > 0 {
		filePath := path.Join(fmt.Sprintf("image-%v.bin", board))
		candidates = append(candidates, filePath)
	}
	candidates = append(candidates, path.Join("image.bin"))
	candidates = append(candidates, path.Join("bios.bin"))

	for i := 0; i < len(candidates); i++ {
		if imageMetadata.IncludesFile(candidates[i]) {
			return extractFileFromImage(ctx, candidates[i], imageMetadata, s)
		}
	}
	return "", fmt.Errorf(`could not find an AP image named any of: %v.
List of files in archive: %v.
Specifying board and model may help`, candidates, imageMetadata.ListOfFiles)
}

// PickAndExtractECImage uses provided list of |filesInArchive| to pick an EC
// image to use, extracts only it, and returns a path to extracted image.
// board and model(aka variant) are optional.
func PickAndExtractECImage(ctx context.Context, s common_utils.ServiceAdapterInterface, imageMetadata ImageArchiveMetadata, board, model string) (string, error) {
	candidates := []string{}
	if len(model) > 0 {
		filePath := path.Join(model, "ec.bin")
		candidates = append(candidates, filePath)
	}
	if len(board) > 0 {
		filePath := path.Join(board, "ec.bin")
		candidates = append(candidates, filePath)
	}
	candidates = append(candidates, path.Join("ec.bin"))

	for i := 0; i < len(candidates); i++ {
		if imageMetadata.IncludesFile(candidates[i]) {
			return extractFileFromImage(ctx, candidates[i], imageMetadata, s)
		}

	}
	return "", fmt.Errorf(`could not find an EC image named any of: %v.
List of files in archive: %v.
Specifying board and model may help`, candidates, imageMetadata.ListOfFiles)
}

// PickAndExtractPDImage uses provided list of |filesInArchive| to pick a PD
// image to use, extracts only it, and returns a path to extracted image.
func PickAndExtractPDImage(ctx context.Context, s common_utils.ServiceAdapterInterface, imageMetadata ImageArchiveMetadata, board, model string) (string, error) {
	candidates := []string{"pd.bin"}

	for i := 0; i < len(candidates); i++ {
		if imageMetadata.IncludesFile(candidates[i]) {
			return extractFileFromImage(ctx, candidates[i], imageMetadata, s)
		}
	}

	return "", fmt.Errorf(`could not find an PD image named any of: %v.
List of files in archive: %v.
Specifying board and model may help`, candidates, imageMetadata.ListOfFiles)
}
