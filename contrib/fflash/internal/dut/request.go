// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dut

import (
	"time"

	"golang.org/x/oauth2"
)

// Request contains everything needed to perform a flash.
type Request struct {
	// Base time when the flash started, for logging.
	ElapsedTimeWhenSent time.Duration

	Token     *oauth2.Token
	Bucket    string
	Directory string

	FlashOptions
}

// FlashOptions for Request.
// Unlike Request.Bucket, Request.Directory, these are determined solely by
// parsing the command line without further processing.
type FlashOptions struct {
	ClobberStateful bool // whether to clobber the stateful partition
	ClearTpmOwner   bool // whether to clean tpm owner on reboot
}

type Result struct {
	RetryDisableRootfsVerification bool
	RetryClearTpmOwner             bool
}
