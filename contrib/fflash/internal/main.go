// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"bytes"
	"context"
	"encoding/gob"
	"fmt"
	"log"
	"os"
	"os/user"
	"path"
	"path/filepath"
	"time"

	"cloud.google.com/go/storage"
	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"google.golang.org/api/option"
	"gopkg.in/ini.v1"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/dut"
	embeddedagent "chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/embedded-agent"
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/ssh"
)

const devFeaturesRootfsVerification = "/usr/libexec/debugd/helpers/dev_features_rootfs_verification"

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
		return nil, fmt.Errorf("cannot lookup user: %w", err)
	}

	botoFile := filepath.Join(u.HomeDir, ".boto")

	// Get the key used by gsutil.py
	boto, err := ini.Load(botoFile)
	if err != nil {
		return nil, fmt.Errorf("cannot load %s: %w (please run `gsutil.py config`)", botoFile, err)
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

type Options struct {
	GS            string // gs:// directory to flash
	ReleaseString string // release string such as R105-14989.0.0
	ReleaseNum    int    // release number such as 105
	Board         string // build target name such as brya
}

func Main(ctx context.Context, t0 time.Time, target string, opts *Options) error {
	if err := embeddedagent.SelfCheck(); err != nil {
		return err
	}

	tkSrc, err := getToken(ctx)
	if err != nil {
		return err
	}

	storageClient, err := storage.NewClient(ctx,
		option.WithTokenSource(tkSrc),
	)
	if err != nil {
		return fmt.Errorf("storage.NewClient failed: %w", err)
	}

	sshClient, err := ssh.DialWithSystemSSH(ctx, target)
	if err != nil {
		return fmt.Errorf("system ssh failed: %w", err)
	}
	defer sshClient.Close()

	dutArch, err := DetectArch(sshClient)
	if err != nil {
		return err
	}
	log.Println("DUT arch:", dutArch)

	var board string
	if opts.GS != "" || opts.Board != "" {
		board = opts.Board
	} else {
		var err error
		board, err = DetectBoard(sshClient)
		if err != nil {
			return fmt.Errorf("cannot detect board of %s: %w. %s", target, err,
				"specify --board or --gs to bypass auto board detection",
			)
		}
		log.Println("DUT board:", board)
	}

	targetBucket, targetDirectory, err := getFlashTarget(ctx, storageClient, board, opts)
	if err != nil {
		return err
	}
	log.Printf("flashing directory: gs://%s", path.Join(targetBucket, targetDirectory))

	req, err := createFlashRequest(ctx, tkSrc, targetBucket, targetDirectory)
	if err != nil {
		return err
	}
	if err := req.Check(ctx, storageClient); err != nil {
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
	var stdin bytes.Buffer
	req.ElapsedTimeWhenSent = time.Since(t0)
	if err := gob.NewEncoder(&stdin).Encode(req); err != nil {
		return fmt.Errorf("failed to write flash request: %w", err)
	}
	session.Stdin = &stdin
	var stdout bytes.Buffer
	session.Stdout = &stdout
	session.Stderr = os.Stderr
	if err := session.Run(agentPath); err != nil {
		return fmt.Errorf("dut-agent failed: %w", err)
	}
	var result dut.Result
	if err := gob.NewDecoder(&stdout).Decode(&result); err != nil {
		return fmt.Errorf("cannot decode dut-agent result: %w", err)
	}

	oldParts, err := DetectPartitions(sshClient)
	if err != nil {
		return err
	}
	log.Println("DUT root is on:", oldParts.ActiveRootfs())

	sshClient, err = CheckedReboot(ctx, sshClient, target, oldParts.InactiveRootfs())
	if err != nil {
		return err
	}

	needs2ndReboot := false

	if result.RetryDisableRootfsVerification {
		log.Println("retrying disable rootfs verification")
		if _, err := sshClient.RunSimpleOutput(devFeaturesRootfsVerification); err != nil {
			return fmt.Errorf("disable rootfs verification failed: %w", err)
		}
		needs2ndReboot = true
	}

	if result.RetryClearTpmOwner {
		log.Println("retrying clear tpm owner")
		if _, err := sshClient.RunSimpleOutput("crossystem clear_tpm_owner_request=1"); err != nil {
			return fmt.Errorf("failed to clear tpm owner: %w", err)
		}
		needs2ndReboot = true
	}

	if needs2ndReboot {
		sshClient, err = CheckedReboot(ctx, sshClient, target, oldParts.InactiveRootfs())
		if err != nil {
			return err
		}
	}

	if _, err := sshClient.RunSimpleOutput(devFeaturesRootfsVerification + " -q"); err != nil {
		return fmt.Errorf("failed to check rootfs verification: %w", err)
	}

	return nil
}
