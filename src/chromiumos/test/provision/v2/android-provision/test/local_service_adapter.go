// Copyright 2023 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package test

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"chromiumos/test/provision/v2/android-provision/common"
	"cloud.google.com/go/storage"

	"go.chromium.org/chromiumos/config/go/test/lab/api"
	"go.chromium.org/luci/common/retry"
	"go.chromium.org/luci/common/retry/transient"
	"golang.org/x/crypto/ssh"
)

const (
	privateKeyFile             = "testing_rsa"
	sshUser                    = "root"
	retryCountOnTransientError = 5
)

// LocalDutServiceAdapter implements Service Adapter interface and used to
// substitute DUT Service in local testing.
type LocalDutServiceAdapter struct {
	client *ssh.Client
}

// parsePrivateKey gets private key for ssh authentication.
func parsePrivateKey() (ssh.Signer, error) {
	keyPath := fmt.Sprintf("%s/.ssh/%s", os.Getenv("HOME"), privateKeyFile)
	buff, _ := os.ReadFile(keyPath)
	return ssh.ParsePrivateKey(buff)
}

// createSshConfig creates ssh client config for our connection.
func createSshConfig() (*ssh.ClientConfig, error) {
	key, err := parsePrivateKey()
	if err != nil {
		return nil, err
	}
	return &ssh.ClientConfig{
		User: sshUser,
		Auth: []ssh.AuthMethod{
			ssh.PublicKeys(key),
		},
		HostKeyCallback: ssh.InsecureIgnoreHostKey(),
	}, nil
}

// retryParams defines retry strategy for handling transient errors.
func retryParams() retry.Iterator {
	return &retry.ExponentialBackoff{
		Limited: retry.Limited{
			Delay:    3 * time.Second,
			Retries:  retryCountOnTransientError,
			MaxTotal: 1 * time.Minute,
		},
		Multiplier: 2,
	}
}

func NewLocalDutServiceAdapter(endPoint *api.IpEndpoint) (*LocalDutServiceAdapter, error) {
	cfg, err := createSshConfig()
	if err != nil {
		return nil, err
	}
	client, err := ssh.Dial("tcp", fmt.Sprintf("%s:%d", endPoint.GetAddress(), endPoint.GetPort()), cfg)
	if err != nil {
		return nil, err
	}
	return &LocalDutServiceAdapter{
		client: client,
	}, nil
}

func (s LocalDutServiceAdapter) RunCmd(ctx context.Context, cmd string, args []string) (string, error) {
	var session *ssh.Session
	err := retry.Retry(ctx, transient.Only(retryParams), func() error {
		var err error
		session, err = s.client.NewSession()
		return err
	}, retry.LogCallback(ctx, "ssh-connect"))
	if err != nil {
		return "", err
	}
	defer session.Close()
	var b bytes.Buffer
	// get output
	session.Stdout = &b
	// Run the command
	err = session.Run(cmd + " " + strings.Join(args[:], " "))
	return b.String(), err
}

func (s LocalDutServiceAdapter) Restart(ctx context.Context) error {
	return errors.New("not implemented")
}

func (s LocalDutServiceAdapter) PathExists(ctx context.Context, path string) (bool, error) {
	return false, errors.New("not implemented")
}

func (s LocalDutServiceAdapter) PipeData(ctx context.Context, sourceUrl string, pipeCommand string) error {
	return errors.New("not implemented")
}

// CopyData mocks the caching service functionality.
// It downloads the apk file from GCP to current directory and copy it remotely to the host.
func (s LocalDutServiceAdapter) CopyData(ctx context.Context, sourceUrl string, destPath string) error {
	fp := strings.Split(sourceUrl, "/")
	apk := fp[len(fp)-1]
	dir := fp[len(fp)-2]
	gsPath := dir + "/" + apk

	err := downloadFile(ctx, gsPath, apk)
	if err != nil {
		return err
	}

	// Copy file to remote.
	var session *ssh.Session
	err = retry.Retry(ctx, transient.Only(retryParams), func() error {
		var err error
		session, err = s.client.NewSession()
		return err
	}, retry.LogCallback(ctx, "ssh-connect"))
	if err != nil {
		return err
	}
	file, err := os.Open(apk)
	if err != nil {
		return err
	}
	defer file.Close()
	stat, err := file.Stat()
	if err != nil {
		return err
	}
	go func() {
		hostIn, _ := session.StdinPipe()
		defer hostIn.Close()
		fmt.Fprintf(hostIn, "C0664 %d %s\n", stat.Size(), apk)
		io.Copy(hostIn, file)
		fmt.Fprint(hostIn, "\x00")
	}()
	// -t option indicates sink mode. Accepting files sent from current ssh connection.
	err = session.Run(fmt.Sprintf("/usr/bin/scp -t /tmp/%s/", dir))
	if err != nil {
		return err
	}
	return nil
}

func (s LocalDutServiceAdapter) CreateDirectories(ctx context.Context, dirs []string) error {
	if _, err := s.RunCmd(ctx, "mkdir", append([]string{"-p"}, dirs...)); err != nil {
		return fmt.Errorf("could not create directory, %w", err)
	}
	return nil
}

func (s LocalDutServiceAdapter) DeleteDirectory(ctx context.Context, dir string) error {
	if _, err := s.RunCmd(ctx, "rm", []string{"-rf", dir}); err != nil {
		return fmt.Errorf("could not delete directory, %w", err)
	}
	return nil
}

// downloadFile downloads a GCP object.
func downloadFile(ctx context.Context, object string, destFileName string) error {
	client, err := storage.NewClient(ctx)
	if err != nil {
		return fmt.Errorf("storage.NewClient: %v", err)
	}
	defer client.Close()

	ctx, cancel := context.WithTimeout(ctx, time.Minute*5)
	defer cancel()

	f, err := os.Create(destFileName)
	if err != nil {
		return fmt.Errorf("os.Create: %v", err)
	}

	rc, err := client.Bucket(common.GSBucketName).Object(object).NewReader(ctx)
	if err != nil {
		return fmt.Errorf("Object(%q).NewReader: %v", object, err)
	}
	defer rc.Close()

	if _, err := io.Copy(f, rc); err != nil {
		return fmt.Errorf("io.Copy: %v", err)
	}

	if err = f.Close(); err != nil {
		return fmt.Errorf("f.Close: %v", err)
	}
	fmt.Fprintf(f, "Blob %v downloaded to local file %v\n", object, destFileName)
	return nil

}
