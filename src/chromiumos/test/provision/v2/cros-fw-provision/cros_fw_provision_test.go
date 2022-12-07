// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-fw-provision/cli"
	firmwareservice "chromiumos/test/provision/v2/cros-fw-provision/service"
	state_machine "chromiumos/test/provision/v2/cros-fw-provision/state-machine"
	mock_common_utils "chromiumos/test/provision/v2/mock-common-utils"
	"context"
	"path/filepath"
	"strings"
	"testing"

	"github.com/golang/mock/gomock"
	conf "go.chromium.org/chromiumos/config/go"
	build_api "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/test/api"
)

func TestDetailedRequestSSHStates(t *testing.T) {
	fakeGSPath := "gs://test-archive.tar.gz"
	fakeGSFilename := filepath.Base(fakeGSPath)

	apImageWithinArchive := "image.bin"
	ecImageWithinArchive := "ec.bin"
	pdImageWithinArchive := "pd.bin"
	imagesWithinArchive := strings.Join([]string{
		"foo",
		apImageWithinArchive,
		"bar",
		ecImageWithinArchive,
		"baz",
		pdImageWithinArchive,
	}, "\n") // as reported by tar

	makeRequest := func(main_rw, main_ro, ec_ro, pd_ro bool) *api.ProvisionFirmwareRequest {
		fakePayload := &build_api.FirmwarePayload{FirmwareImage: &build_api.FirmwarePayload_FirmwareImagePath{FirmwareImagePath: &conf.StoragePath{HostType: conf.StoragePath_GS, Path: fakeGSPath}}}
		FirmwareConfig := build_api.FirmwareConfig{}
		if main_rw {
			FirmwareConfig.MainRwPayload = fakePayload
		}
		if main_ro {
			FirmwareConfig.MainRoPayload = fakePayload
		}
		if ec_ro {
			FirmwareConfig.EcRoPayload = fakePayload
		}
		if pd_ro {
			FirmwareConfig.PdRoPayload = fakePayload
		}
		req := &api.ProvisionFirmwareRequest{
			Board: "test_board",
			Model: "test_model",
		}
		req.FirmwareRequest = &api.ProvisionFirmwareRequest_DetailedRequest{
			DetailedRequest: &FirmwareConfig,
		}

		return req
	}

	checkStateName := func(st common_utils.ServiceState, expectedStateName string) {
		if st == nil {
			if len(expectedStateName) > 0 {
				t.Fatalf("expected state %v. got: nil state", expectedStateName)
			}
			return
		}
		stateName := st.Name()
		if stateName != expectedStateName {
			t.Fatalf("expected state %v. got: %v", expectedStateName, stateName)
		}
	}

	type TestCase struct {
		// inputs
		main_rw, main_ro, ec_ro, pd_ro bool
		// expected outputs
		updateRw, updateRo     bool
		expectConstructorError bool
	}

	testCases := []TestCase{
		{ /*in*/ false, false, false, false /*out*/, false, false /*err*/, true},
		{ /*in*/ true, false, false, false /*out*/, true, false /*err*/, false},
		{ /*in*/ false, true, false, false /*out*/, false, true /*err*/, false},
		{ /*in*/ false, false, true, true /*out*/, false, true /*err*/, false},
		{ /*in*/ false, true, true, true /*out*/, false, true /*err*/, false},
		{ /*in*/ true, true, true, true /*out*/, true, true /*err*/, false},
		{ /*in*/ true, true, false, true /*out*/, true, true /*err*/, false},
	}

	// Set up the mock.
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	log, _ := cli.SetUpLog(cli.DefaultLogDirectory)

	for _, testCase := range testCases {
		// Create FirmwareService.
		ctx := context.Background()
		req := makeRequest(testCase.main_rw, testCase.main_ro, testCase.ec_ro, testCase.pd_ro)
		log.Printf("  Test Case: %#v\n  Detailed Request: %#v", testCase, req)
		fws, err := firmwareservice.NewFirmwareService(
			ctx,
			sam,
			nil,
			req,
		)
		// Check if init error is expected/got.
		if err != nil {
			if testCase.expectConstructorError {
				continue
			}
			t.Fatalf("failed to create FirmwareService with test case %#v: %v", testCase, err)
		}
		if err == nil && testCase.expectConstructorError {
			t.Fatalf("expected constructor error for test case %#v. got: %v", testCase, err)
		}
		// Check expected states.
		if testCase.updateRo != fws.UpdateRo() {
			t.Fatalf("test case %#v expects updateRo to be %v. got: %v.", testCase, testCase.updateRo, fws.UpdateRo())
		}
		if testCase.updateRw != fws.UpdateRw() {
			t.Fatalf("test case %#v expects updateRw to be %v. got: %v.", testCase, testCase.updateRw, fws.UpdateRw())
		}

		// Start with the first state of the service.
		st := state_machine.NewFirmwarePrepareState(fws)
		// Confirm state name is Prepare.
		checkStateName(st, state_machine.PrepareStateName)

		// Set mock expectations.
		gomock.InOrder(
			sam.EXPECT().RunCmd(gomock.Any(), "mktemp", gomock.Any()).Return("", nil),
			sam.EXPECT().CopyData(gomock.Any(), gomock.Eq(fakeGSPath), gomock.Eq(fakeGSFilename)).Return(nil),
			sam.EXPECT().RunCmd(gomock.Any(), "tar", gomock.Any()).Return(imagesWithinArchive, nil),
		)

		// Execute the state and proceed.
		_, err = st.Execute(ctx, log)
		if err != nil {
			t.Fatal(err)
		}
		st = st.Next()

		if testCase.updateRo {
			// Confirm state name is RO.
			checkStateName(st, state_machine.UpdateRoStateName)

			// Set mock expectations.
			expectedFutilityImageArgs := []string{}
			if testCase.main_ro {
				expectedFutilityImageArgs = append(expectedFutilityImageArgs, "--image="+apImageWithinArchive)
				gomock.InOrder(
					sam.EXPECT().RunCmd(gomock.Any(), "cd", gomock.Any()).Return("", nil), // tar
				)
			}
			if testCase.ec_ro {
				expectedFutilityImageArgs = append(expectedFutilityImageArgs, "--ec_image="+ecImageWithinArchive)
				gomock.InOrder(
					sam.EXPECT().RunCmd(gomock.Any(), "cd", gomock.Any()).Return("", nil), // tar
				)
			}
			if testCase.pd_ro {
				expectedFutilityImageArgs = append(expectedFutilityImageArgs, "--pd_image="+pdImageWithinArchive)
				gomock.InOrder(
					sam.EXPECT().RunCmd(gomock.Any(), "cd", gomock.Any()).Return("", nil), // tar
				)
			}
			expectedFutilityArgs := append([]string{"update", "--mode=recovery"}, expectedFutilityImageArgs...)
			expectedFutilityArgs = append(expectedFutilityArgs, "--wp=0")
			gomock.InOrder(
				sam.EXPECT().RunCmd(gomock.Any(), "futility", expectedFutilityArgs).Return("", nil),
			)

			// Execute the state and proceed.
			_, err := st.Execute(ctx, log)
			if err != nil {
				t.Fatal(err)
			}
			st = st.Next()
		}

		if testCase.updateRw {
			// Confirm state name is RW.
			checkStateName(st, state_machine.UpdateRwStateName)

			// Set mock expectations.
			expectedFutilityArgs := []string{"update", "--mode=recovery", "--image=" + apImageWithinArchive, "--wp=1"}
			gomock.InOrder(
				sam.EXPECT().RunCmd(gomock.Any(), "cd", gomock.Any()).Return("", nil), // tar
				sam.EXPECT().RunCmd(gomock.Any(), "futility", expectedFutilityArgs).Return("", nil),
			)

			// Execute the state and proceed.
			_, err := st.Execute(ctx, log)
			if err != nil {
				t.Fatal(err)
			}
			st = st.Next()
		}

		// Confirm state name is postinstall.
		checkStateName(st, state_machine.PostInstallStateName)
		// Set mock expectations.
		gomock.InOrder(
			sam.EXPECT().DeleteDirectory(gomock.Any(), "").Return(nil),
			sam.EXPECT().Restart(gomock.Any()).Return(nil),
			sam.EXPECT().RunCmd(gomock.Any(), "true", nil).Return("", nil),
		)
		// Execute the state and proceed.
		_, err = st.Execute(ctx, log)
		if err != nil {
			t.Fatal(err)
		}
		st = st.Next()

		// Confirm no states left.
		checkStateName(st, "")
	}
}

func TestSimpleRequestSSHStates(t *testing.T) {
	fakeGSPath := "gs://test-archive.tar.gz"
	fakeGSFilename := filepath.Base(fakeGSPath)

	makeRequest := func(gsPath string, flashRo bool) *api.ProvisionFirmwareRequest {
		req := &api.ProvisionFirmwareRequest{
			Board: "test_board",
			Model: "test_model",
		}
		req.FirmwareRequest = &api.ProvisionFirmwareRequest_SimpleRequest{
			SimpleRequest: &api.SimpleFirmwareRequest{
				FlashRo:           flashRo,
				FirmwareImagePath: &conf.StoragePath{HostType: conf.StoragePath_GS, Path: gsPath},
			},
		}

		return req
	}

	checkStateName := func(st common_utils.ServiceState, expectedStateName string) {
		if st == nil {
			if len(expectedStateName) > 0 {
				t.Fatalf("expected state %v. got: nil state", expectedStateName)
			}
			return
		}
		stateName := st.Name()
		if stateName != expectedStateName {
			t.Fatalf("expected state %v. got: %v", expectedStateName, stateName)
		}
	}

	type TestCase struct {
		// inputs
		flashRo    bool
		fakeGSPath string
		// expected outputs
		updateRw, updateRo     bool
		expectConstructorError bool
	}

	testCases := []TestCase{
		{ /*in*/ false, "" /*out*/, false, false /*err*/, true},
		{ /*in*/ true, "" /*out*/, false, false /*err*/, true},
		{ /*in*/ false, fakeGSPath /*out*/, true, false /*err*/, false},
		{ /*in*/ true, fakeGSPath /*out*/, false, true /*err*/, false},
	}

	// Set up the mock.
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()
	sam := mock_common_utils.NewMockServiceAdapterInterface(ctrl)
	log, _ := cli.SetUpLog(cli.DefaultLogDirectory)

	for _, testCase := range testCases {
		// Create FirmwareService.
		ctx := context.Background()
		req := makeRequest(testCase.fakeGSPath, testCase.flashRo)
		log.Printf("  Test Case: %#v\n  Simple Request: %#v", testCase, req)

		fws, err := firmwareservice.NewFirmwareService(
			ctx,
			sam,
			nil,
			req,
		)
		// Check if init error is expected/got.
		if err != nil {
			if testCase.expectConstructorError {
				continue
			}
			t.Fatalf("failed to create FirmwareService with test case %#v: %v", testCase, err)
		}
		if err == nil && testCase.expectConstructorError {
			t.Fatalf("expected constructor error for test case %#v. got: %v", testCase, err)
		}
		// Check expected states.
		if testCase.updateRo != fws.UpdateRo() {
			t.Fatalf("test case %#v expects updateRo to be %v. got: %v.", testCase, testCase.updateRo, fws.UpdateRo())
		}
		if testCase.updateRw != fws.UpdateRw() {
			t.Fatalf("test case %#v expects updateRw to be %v. got: %v.", testCase, testCase.updateRw, fws.UpdateRw())
		}

		// Start with the first state of the service.
		st := state_machine.NewFirmwarePrepareState(fws)
		// Confirm state name is Prepare.
		checkStateName(st, state_machine.PrepareStateName)

		// Set mock expectations.
		gomock.InOrder(
			sam.EXPECT().RunCmd(gomock.Any(), "mktemp", gomock.Any()).Return("", nil),
			sam.EXPECT().CopyData(gomock.Any(), gomock.Eq(fakeGSPath), gomock.Eq(fakeGSFilename)).Return(nil),
		)

		// Execute the state and proceed.
		_, err = st.Execute(ctx, log)
		if err != nil {
			t.Fatal(err)
		}
		st = st.Next()

		if testCase.flashRo {
			// Confirm state name is RO.
			checkStateName(st, state_machine.UpdateRoStateName)
		} else {
			// Confirm state name is RW.
			checkStateName(st, state_machine.UpdateRwStateName)
		}

		// Set mock expectations.
		expectedFutilityArgs := []string{"update", "--mode=recovery", "--archive=" + fakeGSFilename}

		if testCase.updateRo {
			expectedFutilityArgs = append(expectedFutilityArgs, "--wp=0")
		} else {
			expectedFutilityArgs = append(expectedFutilityArgs, "--wp=1")
		}
		gomock.InOrder(
			sam.EXPECT().RunCmd(gomock.Any(), "futility", expectedFutilityArgs).Return("", nil),
		)

		// Execute the state and proceed.
		_, err = st.Execute(ctx, log)
		if err != nil {
			t.Fatal(err)
		}
		st = st.Next()

		// Confirm state name is postinstall.
		checkStateName(st, state_machine.PostInstallStateName)
		// Set mock expectations.
		gomock.InOrder(
			sam.EXPECT().DeleteDirectory(gomock.Any(), "").Return(nil),
			sam.EXPECT().Restart(gomock.Any()).Return(nil),
			sam.EXPECT().RunCmd(gomock.Any(), "true", nil).Return("", nil),
		)
		// Execute the state and proceed.
		_, err = st.Execute(ctx, log)
		if err != nil {
			t.Fatal(err)
		}
		st = st.Next()

		// Confirm no states left.
		checkStateName(st, "")
	}
}
