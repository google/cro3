// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package site

import (
	"fmt"

	"go.chromium.org/luci/grpc/prpc"
)

var DefaultPRPCOptions = prpcOptionWithUserAgent(fmt.Sprintf("ctp-lib/%d", VersionNumber))
var VersionNumber = 1

// prpcOptionWithUserAgent create prpc option with custom UserAgent.
// DefaultOptions provides Retry ability in case we have issue with service.
func prpcOptionWithUserAgent(userAgent string) *prpc.Options {
	options := *prpc.DefaultOptions()
	options.UserAgent = userAgent
	return &options
}
