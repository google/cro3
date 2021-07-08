// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package lacrosservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
)

// Third step of LaCrOSInstall State Machine. Currently a noop, to be implemented
type LaCrOSVerifyState struct {
	service LaCrOSService
}

func (s LaCrOSVerifyState) Execute(ctx context.Context) error {
	return nil
}

func (s LaCrOSVerifyState) Next() services.ServiceState {
	return nil
}

func (s LaCrOSVerifyState) Name() string {
	return "LaCrOS Verify"
}
