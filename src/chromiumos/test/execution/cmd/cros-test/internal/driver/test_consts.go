// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package driver implements drivers to execute tests.
package driver

import (
	"go.chromium.org/chromiumos/config/go/test/api"
	labapi "go.chromium.org/chromiumos/config/go/test/lab/api"
)

// Common test data for multiple tests.
const (
	reqName1   = "PassedTest1"
	reqName2   = "SkippedTest1"
	reqName3   = "PassedTest2"
	reqName4   = "SkippedTest2"
	reqName5   = "FailedTest1"
	suite1     = "suite1"
	suite2     = "suite2"
	test1      = "launcher.PinAppToShelf.clamshell_mode"
	test2      = "launcher.PinAppToShelf.tablet_mode"
	test3      = "launcher.CreateAndRenameFolder.clamshell_mode"
	test4      = "launcher.CreateAndRenameFolder.tablet_mode"
	test5      = "meta.LocalFail"
	workDir1   = "/tmp/tast/result1"
	workDir2   = "/tmp/tast/result2"
	sinkPort   = 22
	tlsAddress = "192.168.86.81"
	tlsPort    = 2227
	tlwAddress = "192.168.86.109:2228"
	dutName1   = "dut1"
	dutPort1   = 2225
	dut1       = "dut1:2225"
)

var req = api.CrosTestRequest{
	TestSuites: []*api.TestSuite{
		{
			Name: suite1,
			Spec: &api.TestSuite_TestCaseIds{
				TestCaseIds: &api.TestCaseIdList{
					TestCaseIds: []*api.TestCase_Id{
						{
							Value: test1,
						},
						{
							Value: test2,
						},
						{
							Value: test3,
						},
					},
				},
			},
		},
		{
			Name: suite2,
			Spec: &api.TestSuite_TestCaseIds{
				TestCaseIds: &api.TestCaseIdList{
					TestCaseIds: []*api.TestCase_Id{
						{
							Value: test4,
						},
						{
							Value: test5,
						},
					},
				},
			},
		},
	},
	Primary: &api.CrosTestRequest_Device{
		Dut: &labapi.Dut{
			Id: &labapi.Dut_Id{Value: "Dut1"},
			DutType: &labapi.Dut_Chromeos{
				Chromeos: &labapi.Dut_ChromeOS{
					Ssh: &labapi.IpEndpoint{Address: dutName1, Port: dutPort1},
				},
			},
		},
	},
}
