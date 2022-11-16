// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"log"
	"os"
	"path/filepath"

	"chromiumos/test/provision/v2/android-provision/common/zip"
	"chromiumos/test/provision/v2/android-provision/service"
)

type ExtractAPKFileCommand struct {
	ctx context.Context
	svc *service.AndroidService
	zip zip.ZipReader
}

func NewExtractAPKFileCommand(ctx context.Context, svc *service.AndroidService) *ExtractAPKFileCommand {
	return &ExtractAPKFileCommand{
		ctx: ctx,
		svc: svc,
		zip: &zip.Zip{},
	}
}

func (c *ExtractAPKFileCommand) Execute(log *log.Logger) error {
	log.Printf("Start ExtractAPKFileCommand Execute")
	for _, pkg := range c.svc.ProvisionPackages {
		if cipdPkg := pkg.CIPDPackage; cipdPkg.FilePath != "" {
			dstPath := filepath.Join(c.svc.ProvisionDir, cipdPkg.InstanceId)
			if _, err := os.Stat(dstPath); !os.IsNotExist(err) {
				continue
			}
			err := c.zip.UnzipFile(cipdPkg.FilePath, dstPath)
			if err != nil {
				log.Printf("ExtractAPKFileCommand Failure: %v", err)
				return err
			}
		}
	}
	log.Printf("ExtractAPKFileCommand Success")
	return nil
}

func (c *ExtractAPKFileCommand) Revert() error {
	return nil
}

func (c *ExtractAPKFileCommand) GetErrorMessage() string {
	return "failed to extract APK file"
}
