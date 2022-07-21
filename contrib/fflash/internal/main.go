// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"context"
	"encoding/gob"
	"fmt"
	"log"
	"os"
	"os/user"
	"path/filepath"
	"time"

	"cloud.google.com/go/storage"
	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"google.golang.org/api/option"
	"gopkg.in/ini.v1"

	embeddedagent "chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/embedded-agent"
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/ssh"
)

// getToken returns the user's token to access Google Cloud Storage.
// It reads ~/.boto, which is a ini file set up by `gsutil.py config`.
func getToken(ctx context.Context) (oauth2.TokenSource, error) {
	// Impersonate gsutil
	// https://github.com/GoogleCloudPlatform/gsutil/blob/7bad311bd5444907c515ff745429cc2ffd31b22d/gslib/utils/system_util.py#L174
	c := oauth2.Config{
		ClientID:     "909320924072.apps.googleusercontent.com",
		ClientSecret: "p3RlpR10xMFh9ZXBS/ZNLYUu",
		Endpoint:     google.Endpoint,
	}

	u, err := user.Current()
	if err != nil {
		return nil, fmt.Errorf("cannot lookup user: %s", err)
	}

	botoFile := filepath.Join(u.HomeDir, ".boto")

	// Get the key used by gsutil.py
	boto, err := ini.Load(botoFile)
	if err != nil {
		return nil, fmt.Errorf("cannot load %s: %s (please run `gsutil.py config`)", botoFile, err)
	}
	refreshToken := boto.Section("Credentials").Key("gs_oauth2_refresh_token").String()
	if refreshToken == "" {
		return nil, fmt.Errorf("cannot get refresh token from %s (please run `gsutil.py config`)", refreshToken)
	}

	ts := c.TokenSource(
		ctx,
		&oauth2.Token{
			RefreshToken: refreshToken,
		},
	)

	return ts, nil
}

func Main(ctx context.Context, t0 time.Time, target string) error {
	tkSrc, err := getToken(ctx)
	if err != nil {
		return err
	}

	sshClient, err := ssh.DialWithSystemSSH(ctx, target)
	if err != nil {
		return fmt.Errorf("system ssh failed: %s", err)
	}
	defer sshClient.Close()

	dutReleasePath, err := DetectReleaseBuilder(sshClient)
	if err != nil {
		return fmt.Errorf("cannot detect release for dut: %s", err)
	}
	log.Println("DUT is running:", dutReleasePath)

	dutArch, err := DetectArch(sshClient)
	if err != nil {
		return err
	}
	log.Println("DUT arch:", dutArch)

	storageClient, err := storage.NewClient(ctx,
		option.WithTokenSource(tkSrc),
	)
	if err != nil {
		return fmt.Errorf("storage.NewClient failed: %s", err)
	}

	gsRelease, err := GetLatestReleaseForBoard(ctx, storageClient, dutReleasePath.Board)
	if err != nil {
		return err
	}

	targetBucket := "chromeos-image-archive"
	targetDirectory := fmt.Sprintf("%s-release/%s", dutReleasePath.Board, gsRelease)
	log.Printf("flashing directory: gs://%s/%s", targetBucket, targetDirectory)

	req, err := createFlashRequest(ctx, tkSrc, targetBucket, targetDirectory)
	if err != nil {
		return err
	}

	log.Println("pushing dut-agent to", target)
	bin, err := embeddedagent.ExecutableForArch(dutArch)
	if err != nil {
		return err
	}
	agentPath, err := PushCompressedExecutable(ctx, sshClient, bin)
	if err != nil {
		return err
	}
	log.Println("agent pushed to", agentPath)

	session, err := sshClient.NewSession()
	if err != nil {
		return err
	}
	stdin, err := session.StdinPipe()
	if err != nil {
		return err
	}
	session.Stdout = os.Stdout
	session.Stderr = os.Stderr
	if err := session.Start(agentPath); err != nil {
		return err
	}

	req.ElapsedTimeWhenSent = time.Since(t0)
	go func() {
		if err := gob.NewEncoder(stdin).Encode(req); err != nil {
			log.Printf("failed to write flash request: %s", err)
		}
		if err := stdin.Close(); err != nil {
			log.Printf("failed to finish flash request: %s", err)
		}
	}()

	if err := session.Wait(); err != nil {
		return fmt.Errorf("dut-agent failed: %s", err)
	}

	return nil
}
