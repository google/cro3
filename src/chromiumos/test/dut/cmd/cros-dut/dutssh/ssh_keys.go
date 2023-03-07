// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dutssh

import (
	"fmt"
	"io/ioutil"
	"os"

	"golang.org/x/crypto/ssh"
)

// The provided key is copied from
// https://chromium.googlesource.com/chromiumos/chromite/+/HEAD/ssh_keys/testing_rsa
// It's a well known "private" key used widely in Chrome OS testing.
const sshKeyContent = `
-----BEGIN RSA PRIVATE KEY-----
MIIEoAIBAAKCAQEAvsNpFdK5lb0GfKx+FgsrsM/2+aZVFYXHMPdvGtTz63ciRhq0
Jnw7nln1SOcHraSz3/imECBg8NHIKV6rA+B9zbf7pZXEv20x5Ul0vrcPqYWC44PT
tgsgvi8s0KZUZN93YlcjZ+Q7BjQ/tuwGSaLWLqJ7hnHALMJ3dbEM9fKBHQBCrG5H
OaWD2gtXj7jp04M/WUnDDdemq/KMg6E9jcrJOiQ39IuTpas4hLQzVkKAKSrpl6MY
2etHyoNarlWhcOwitArEDwf3WgnctwKstI/MTKB5BTpO2WXUNUv4kXzA+g8/l1al
jIG13vtd9A/IV3KFVx/sLkkjuZ7z2rQXyNKuJwIBIwKCAQA79EWZJPh/hI0CnJyn
16AEXp4T8nKDG2p9GpCiCGnq6u2Dvz/u1pZk97N9T+x4Zva0GvJc1vnlST7objW/
Y8/ET8QeGSCT7x5PYDqiVspoemr3DCyYTKPkADKn+cLAngDzBXGHDTcfNP4U6xfr
Qc5JK8BsFR8kApqSs/zCU4eqBtp2FVvPbgUOv3uUrFnjEuGs9rb1QZ0K6o08L4Cq
N+e2nTysjp78blakZfqlurqTY6iJb0ImU2W3T8sV6w5GP1NT7eicXLO3WdIRB15a
evogPeqtMo8GcO62wU/D4UCvq4GNEjvYOvFmPzXHvhTxsiWv5KEACtleBIEYmWHA
POwrAoGBAOKgNRgxHL7r4bOmpLQcYK7xgA49OpikmrebXCQnZ/kZ3QsLVv1QdNMH
Rx/ex7721g8R0oWslM14otZSMITCDCMWTYVBNM1bqYnUeEu5HagFwxjQ2tLuSs8E
SBzEr96JLfhwuBhDH10sQqn+OQG1yj5acs4Pt3L4wlYwMx0vs1BxAoGBANd9Owro
5ONiJXfKNaNY/cJYuLR+bzGeyp8oxToxgmM4UuA4hhDU7peg4sdoKJ4XjB9cKMCz
ZGU5KHKKxNf95/Z7aywiIJEUE/xPRGNP6tngRunevp2QyvZf4pgvACvk1tl9B3HH
7J5tY/GRkT4sQuZYpx3YnbdP5Y6Kx33BF7QXAoGAVCzghVQR/cVT1QNhvz29gs66
iPIrtQnwUtNOHA6i9h+MnbPBOYRIpidGTaqEtKTTKisw79JjJ78X6TR4a9ML0oSg
c1K71z9NmZgPbJU25qMN80ZCph3+h2f9hwc6AjLz0U5wQ4alP909VRVIX7iM8paf
q59wBiHhyD3J16QAxhsCgYBu0rCmhmcV2rQu+kd4lCq7uJmBZZhFZ5tny9MlPgiK
zIJkr1rkFbyIfqCDzyrU9irOTKc+iCUA25Ek9ujkHC4m/aTU3lnkNjYp/OFXpXF3
XWZMY+0Ak5uUpldG85mwLIvATu3ivpbyZCTFYM5afSm4StmaUiU5tA+oZKEcGily
jwKBgBdFLg+kTm877lcybQ04G1kIRMf5vAXcConzBt8ry9J+2iX1ddlu2K2vMroD
1cP/U/EmvoCXSOGuetaI4UNQwE/rGCtkpvNj5y4twVLh5QufSOl49V0Ut0mwjPXw
HfN/2MoO07vQrjgsFylvrw9A79xItABaqKndlmqlwMZWc9Ne
-----END RSA PRIVATE KEY-----
`

// readPrivateKey reads and decodes a passphraseless private SSH key from path.
// rok is true if the key data was read successfully off disk and false if it wasn't.
// Note that err may be set while rok is true if the key was malformed or passphrase-protected.
func readPrivateKey(path string) (s ssh.Signer, err error) {
	k, err := ioutil.ReadFile(path)
	if err != nil {
		return nil, err
	}
	s, err = ssh.ParsePrivateKey(k)
	return s, err
}

var testingSSHMethods []ssh.AuthMethod

func init() {
	testingSSHMethods = make([]ssh.AuthMethod, 0)
	setSigners := func(ks []ssh.Signer) {
		testingSSHMethods = append(testingSSHMethods, ssh.PublicKeys(ks...))
	}
	var err error
	keySigners := make([]ssh.Signer, 0)
	testingSSHSigner, err := ssh.ParsePrivateKey([]byte(sshKeyContent))
	if err != nil {
		panic(fmt.Sprintf("The well known RSA key: %v", err.Error()))
	}
	keySigners = append(keySigners, testingSSHSigner)
	p := "/~/.ssh/partner_testing_rsa"
	if _, err := os.Stat(p); os.IsNotExist(err) {
		setSigners(keySigners)
		return
	}

	s, err := readPrivateKey(p)
	if err != nil {
		setSigners(keySigners)
		return
	}
	keySigners = append(keySigners, s)
	setSigners(keySigners)

}