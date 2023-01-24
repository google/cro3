// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ssh

import (
	_ "embed"
	"errors"
	"fmt"
	"log"
	"os"
	"os/user"
	"path/filepath"

	"golang.org/x/crypto/ssh"
)

// SSH RSA private key embedded as bytes.
// https://chromium.googlesource.com/chromiumos/chromite/+/main/ssh_keys/testing_rsa
//
//go:embed testing_rsa
var testingRSA []byte

const (
	testingRSAFileName        = "testing_rsa"
	partnerTestingRSAFileName = "partner_testing_rsa"
)

type KeyChain struct {
	parsedKeys []ssh.Signer

	// Temporary directory holding the private keys
	dir string
	// List of private keys
	files []string
}

// getPartnerTestingRSA attempts to read the partner_testing_rsa from the
// user's ~/.ssh directory.
func getPartnerTestingRSA() ([]byte, error) {
	u, err := user.Current()
	if err != nil {
		return nil, err
	}
	if u.HomeDir == "" {
		return nil, errors.New("cannot determine home directory")
	}
	partnerTestingRSAFile := filepath.Join(u.HomeDir, ".ssh", partnerTestingRSAFileName)
	return os.ReadFile(partnerTestingRSAFile)
}

// NewKeyChain creates a KeyChain holding bundled SSH keys.
//
// KeyChain.Delete() must be called to clean up resources.
func NewKeyChain() (*KeyChain, error) {
	tempDir, err := os.MkdirTemp("", "fflash-keychain-*")
	if err != nil {
		return nil, err
	}

	kc := &KeyChain{dir: tempDir}

	if err := kc.addKeyBytes(testingRSAFileName, testingRSA); err != nil {
		kc.Delete()
		return nil, err
	}

	partnerTestingRSA, err := getPartnerTestingRSA()
	if err != nil {
		log.Printf("Not using partner key: cannot read ~/.ssh/%s: %s", partnerTestingRSAFileName, err)
	} else {
		if err := kc.addKeyBytes(partnerTestingRSAFileName, partnerTestingRSA); err != nil {
			kc.Delete()
			return nil, err
		}
	}

	return kc, nil
}

func (kc *KeyChain) addKeyBytes(name string, b []byte) error {
	key, err := ssh.ParsePrivateKey(b)
	if err != nil {
		return fmt.Errorf("Cannot parse private key %q: %v", name, err)
	}
	kc.parsedKeys = append(kc.parsedKeys, key)

	path := filepath.Join(kc.dir, name)
	if err := os.WriteFile(path, b, 0400); err != nil {
		return err
	}

	kc.files = append(kc.files, path)
	return nil
}

// SSHAuthMethod returns a ssh.AuthMethod using the keys in the KeyChain.
func (kc *KeyChain) SSHAuthMethod() ssh.AuthMethod {
	return ssh.PublicKeys(kc.parsedKeys...)
}

// SSHCommandOptions returns ssh command line options that uses the keys.
func (kc *KeyChain) SSHCommandOptions() []string {
	var opts []string
	for _, keyPath := range kc.files {
		opts = append(opts, fmt.Sprintf("-oIdentityFile=%s", keyPath))
	}
	return opts
}

// Delete cleans up the key chain
func (kc *KeyChain) Delete() error {
	return os.RemoveAll(kc.dir)
}
