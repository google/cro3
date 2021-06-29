// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Third step in the CrOSInstall State Machine. Currently a noop, to be implemented
package crosservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
)

type CrOSVerifyState struct {
	service CrOSService
}

func (s CrOSVerifyState) Execute(ctx context.Context) error {
	// Currently there is no verification post step as we don't specify install type
	return nil
}

func (s CrOSVerifyState) Next() services.ServiceState {
	return CrOSProvisionDLCState{
		service: s.service,
	}
}

func (s CrOSVerifyState) Name() string {
	return "CrOS Verify"
}
