// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Third step in the LaCrOSInstall State Machine. Currently a noop, to be implemented
package state_machine

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/lacros-provision/service"
	"context"
	"log"

	"google.golang.org/protobuf/types/known/anypb"
)

type LaCrOSVerifyState struct {
	service *service.LaCrOSService
}

func (s LaCrOSVerifyState) Execute(ctx context.Context, log *log.Logger) (*anypb.Any, error) {
	log.Printf("Executing %s State:\n", s.Name())
	// Currently there is no verification post step as we don't specify install type
	return nil, nil
}

func (s LaCrOSVerifyState) Next() common_utils.ServiceState {
	return nil
}

func (s LaCrOSVerifyState) Name() string {
	return "LaCrOS Verify"
}
