// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ssh

import _ "embed"

// SSH RSA private key embedded as bytes.
// https://chromium.googlesource.com/chromiumos/chromite/+/main/ssh_keys/testing_rsa
//
//go:embed testing_rsa
var TestingRSA []byte
