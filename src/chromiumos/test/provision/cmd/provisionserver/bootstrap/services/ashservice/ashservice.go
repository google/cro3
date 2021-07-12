// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// AshInstall state machine construction and helper

package ashservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"
	"log"
	"path/filepath"
	"time"

	conf "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"
)

// File specific consts
const (
	autotestDir      = "/usr/local/autotest/deps/chrome_test/test_src/out/Release/"
	stagingDirectory = "/tmp/_tls_chrome_deploy"
	targetDir        = "/opt/google/chrome"
	tastDir          = "/usr/local/libexec/chrome-binary-tests/"
)

// Time specific consts
const (
	twoSeconds = 2 * time.Second
	tenSeconds = 10 * time.Second
)

// binaries to be copied in installation
var copyPaths = [...]string{
	"ash_shell",
	"aura_demo",
	"chrome",
	"chrome-wrapper",
	"chrome.pak",
	"chrome_100_percent.pak",
	"chrome_200_percent.pak",
	"content_shell",
	"content_shell.pak",
	"extensions/",
	"lib/*.so",
	"libffmpegsumo.so",
	"libpdf.so",
	"libppGoogleNaClPluginChrome.so",
	"libosmesa.so",
	"libwidevinecdmadapter.so",
	"libwidevinecdm.so",
	"locales/",
	"nacl_helper_bootstrap",
	"nacl_irt_*.nexe",
	"nacl_helper",
	"resources/",
	"resources.pak",
	"xdg-settings",
	"*.png",
}

// test binaries to be copied in installation
var testPaths = [...]string{
	"*test",
	"*tests",
}

// AshService inherits ServiceInterface
type AshService struct {
	connection services.ServiceAdapterInterface
	imagePath  *conf.StoragePath
}

func NewAshService(dutName string, dutClient api.DutServiceClient, wiringConn *grpc.ClientConn, req *api.InstallAshRequest) AshService {
	service := AshService{
		connection: services.NewServiceAdapter(dutName, dutClient, wiringConn),
		imagePath:  req.AshImagePath,
	}

	return service
}

// NewAshServiceFromExistingConnection is equivalent to the above constructor,
// but recycles a ServiceAdapter. Generally useful for tests.
func NewAshServiceFromExistingConnection(conn services.ServiceAdapterInterface, imagePath *conf.StoragePath) AshService {
	return AshService{
		connection: conn,
		imagePath:  imagePath,
	}
}

// GetFirstState returns the first state of this state machine
func (a *AshService) GetFirstState() services.ServiceState {
	return AshPrepareState{
		service: *a,
	}
}

// CleanUpStagingDirectory simply deletes the staging directory
func (a *AshService) CleanUpStagingDirectory(ctx context.Context) error {
	return a.connection.DeleteDirectory(ctx, stagingDirectory)
}

// CreateStagingDirectory ensures a clean staging directory is present
func (a AshService) CreateStagingDirectory(ctx context.Context) error {
	if err := a.CleanUpStagingDirectory(ctx); err != nil {
		return err
	}

	return a.connection.CreateDirectories(ctx, []string{stagingDirectory})
}

// CreateBinaryDirectories creates all directories which will house the binaries for the install
func (a *AshService) CreateBinaryDirectories(ctx context.Context) error {
	return a.connection.CreateDirectories(ctx, []string{targetDir, autotestDir, tastDir})
}

// CopyImageToDUT copies the desired image to the DUT, passing through the caching layer.
func (a *AshService) CopyImageToDUT(ctx context.Context) error {
	if a.imagePath.HostType == conf.StoragePath_LOCAL || a.imagePath.HostType == conf.StoragePath_HOSTTYPE_UNSPECIFIED {
		return fmt.Errorf("only GS copying is implemented")
	}
	url, err := a.connection.CopyData(ctx, a.imagePath.GetPath())
	if err != nil {
		return fmt.Errorf("failed to cache ash compressed, %w", err)
	}
	if _, err := a.connection.RunCmd(ctx, "", []string{
		"curl", url,
		"|",
		"tar", "--ignore-command-error", "--overwrite", "--preserve-permissions", fmt.Sprintf("--directory=%s", stagingDirectory), "-xf", "-",
	}); err != nil {
		return fmt.Errorf("failed to copy ash compressed, %w", err)
	}

	return nil
}

// MountRootFS mounts the root filesystem as a read/write
func (a *AshService) MountRootFS(ctx context.Context) error {
	if _, err := a.connection.RunCmd(ctx, "mount", []string{"-o", "remount,rw", "/"}); err != nil {
		return fmt.Errorf("could not mount root file system, %w", err)
	}
	return nil
}

// isChromeInUse determines if chrome is currently running
func (a *AshService) isChromeInUse(ctx context.Context) bool {
	_, err := a.connection.RunCmd(ctx, "lsof", []string{fmt.Sprintf("%s/chrome", targetDir)})
	return err != nil
}

// StopChrome stops the UI
func (a *AshService) StopChrome(ctx context.Context) error {
	if _, err := a.connection.RunCmd(ctx, "stop", []string{"ui"}); err != nil {
		// stop ui returns error when UI is terminated, so ignore error here
		log.Printf("failed to stop chrome, %s", err)
	}
	return nil
}

// KillChrome tries to pkill chrome, retrying/re-polling every two seconds
func (a *AshService) KillChrome(ctx context.Context) error {
	for start := time.Now(); time.Since(start) < tenSeconds; time.Sleep(twoSeconds) {
		if !a.isChromeInUse(ctx) {
			return nil
		}
		log.Printf("chrome binary is still running, killing...")
		if _, err := a.connection.RunCmd(ctx, "pkill", []string{"'chrome|session_manager'"}); err != nil {
			return fmt.Errorf("failed run pkill, %s", err)
		}
	}
	return fmt.Errorf("failed to kill chrome")
}

// Deploy rsyncs files relevant to the install to the correct bin locations
func (a *AshService) Deploy(ctx context.Context) error {
	for _, file := range copyPaths {
		if err := a.deployFile(ctx, file, targetDir); err != nil {
			return fmt.Errorf("could not deploy copy file, %w", err)
		}
	}
	for _, file := range testPaths {
		if err := a.deployFile(ctx, file, autotestDir); err != nil {
			return fmt.Errorf("could not deploy autotest file, %w", err)
		}
		if err := a.deployFile(ctx, file, tastDir); err != nil {
			return fmt.Errorf("could not deploy tast file, %w", err)
		}
	}
	return nil
}

// deployFile rsyncs one specific file to the desired bin dir
func (a *AshService) deployFile(ctx context.Context, file string, destination string) error {
	source := fmt.Sprintf("%s/%s", stagingDirectory, file)
	target := filepath.Dir(fmt.Sprintf("%s/%s", destination, file))

	if exists, err := a.connection.PathExists(ctx, source); err != nil {
		return fmt.Errorf("failed to determine file existance, %s", err)
	} else if !exists {
		return nil
	}

	if _, err := a.connection.RunCmd(ctx, "rsync", []string{"-av", source, target}); err != nil {
		return fmt.Errorf("failed run rsync, %s", err)
	}
	return nil
}

// ReloadBus kill the bus daemon with a SIGHUP
func (a *AshService) ReloadBus(ctx context.Context) error {
	if _, err := a.connection.RunCmd(ctx, "killall", []string{"-HUP", "dbus-daemon"}); err != nil {
		return fmt.Errorf("failed to reload dbus, %s", err)
	}
	return nil
}

// StartChrome restarts the ui
func (a *AshService) StartChrome(ctx context.Context) error {
	if _, err := a.connection.RunCmd(ctx, "start", []string{"ui"}); err != nil {
		return fmt.Errorf("failed to start ui, %s", err)
	}
	return nil
}
