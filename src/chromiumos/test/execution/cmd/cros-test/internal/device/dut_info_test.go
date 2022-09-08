// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package device_test tests the exported APIs of the package device.
package device

import (
	"testing"

	"github.com/google/go-cmp/cmp"
	"go.chromium.org/chromiumos/config/go/test/api"
	labapi "go.chromium.org/chromiumos/config/go/test/lab/api"
)

type expectEndpointResult struct {
	ip       *labapi.IpEndpoint
	expected string
}

// TestAddress the function Address to return the addresses of DUTs.
func TestAddress(t *testing.T) {
	data := []expectEndpointResult{
		{
			ip:       &labapi.IpEndpoint{Address: "127.0.0.1", Port: 0},
			expected: "127.0.0.1",
		},
		{
			ip:       &labapi.IpEndpoint{Address: "0:0:0:0:0:ffff:7f00:1", Port: 2},
			expected: "[0:0:0:0:0:ffff:7f00:1]:2",
		},
		{
			ip:       &labapi.IpEndpoint{Address: "0:0:0:0:0:ffff:7f00:1", Port: 0},
			expected: "0:0:0:0:0:ffff:7f00:1",
		},
		{
			ip:       &labapi.IpEndpoint{Address: "chromeos6-row17-rack5-host15.cros.corp.google.com", Port: 0},
			expected: "chromeos6-row17-rack5-host15.cros.corp.google.com",
		},
		{
			ip:       &labapi.IpEndpoint{Address: "chromeos6-row17-rack5-host15", Port: 2555},
			expected: "chromeos6-row17-rack5-host15:2555",
		},
	}

	for _, d := range data {
		device := api.CrosTestRequest_Device{
			Dut: &labapi.Dut{
				Id:      &labapi.Dut_Id{Value: "AnyId"},
				DutType: &labapi.Dut_Chromeos{Chromeos: &labapi.Dut_ChromeOS{Ssh: d.ip}},
			},
		}
		got, err := Address(&device)
		if err != nil {
			t.Errorf("Cannot get address for dut %v: %v", &device, err)
		}
		if got != d.expected {
			t.Errorf("Got %q from Address; wanted:%q", got, d.expected)
		}
	}
}

// TestFillDUTInfo makes sure FillDUTInfo behaved as expected.
func TestFillDUTInfo(t *testing.T) {
	expected := []*DutInfo{
		{
			Addr:            "127.0.0.1:2222",
			Role:            "",
			Servo:           "c6-r9-r7-labstation:9996",
			DutServer:       "cros-dut0:80",
			ProvisionServer: "cros-provision0:80",
			ServoHostname:   "c6-r9-r7-labstation",
			ServoPort:       "9996",
		},
		{
			Addr:            "[0:0:0:0:0:ffff:7f00:1]:2",
			Role:            "cd1",
			Servo:           "c6-r8-r7-labstation:9999",
			DutServer:       "cros-dut1:80",
			ProvisionServer: "cros-provision1:80",
			ServoHostname:   "c6-r8-r7-labstation",
			ServoPort:       "9999",
		},
		{
			Addr:            "c6-r8-rack7-host7",
			Role:            "cd2",
			Servo:           "c6-r7-r7-labstation:9999",
			DutServer:       "cros-dut2:80",
			ProvisionServer: "cros-provision2:80",
			ServoHostname:   "c6-r7-r7-labstation",
			ServoPort:       "9999",
		},
		{
			Addr:            "0:0:0:0:0:ffff:7f00:1",
			Role:            "cd3",
			Servo:           "",
			DutServer:       "",
			ProvisionServer: "",
		},
	}
	input := []*api.CrosTestRequest_Device{
		{
			Dut: &labapi.Dut{
				Id: &labapi.Dut_Id{Value: "AnyId"},
				DutType: &labapi.Dut_Chromeos{
					Chromeos: &labapi.Dut_ChromeOS{
						Ssh: &labapi.IpEndpoint{Address: "127.0.0.1", Port: 2222},
						Servo: &labapi.Servo{
							Present: true,
							ServodAddress: &labapi.IpEndpoint{
								Address: "c6-r9-r7-labstation",
								Port:    9996,
							},
						},
					},
				},
			},
			DutServer:       &labapi.IpEndpoint{Address: "cros-dut0", Port: 80},
			ProvisionServer: &labapi.IpEndpoint{Address: "cros-provision0", Port: 80},
		},
		{
			Dut: &labapi.Dut{
				Id: &labapi.Dut_Id{Value: "AnyId"},
				DutType: &labapi.Dut_Chromeos{
					Chromeos: &labapi.Dut_ChromeOS{
						Ssh: &labapi.IpEndpoint{Address: "0:0:0:0:0:ffff:7f00:1", Port: 2},
						Servo: &labapi.Servo{
							Present: true,
							ServodAddress: &labapi.IpEndpoint{
								Address: "c6-r8-r7-labstation",
								Port:    9999,
							},
						},
					},
				},
			},
			DutServer:       &labapi.IpEndpoint{Address: "cros-dut1", Port: 80},
			ProvisionServer: &labapi.IpEndpoint{Address: "cros-provision1", Port: 80},
		},
		{
			Dut: &labapi.Dut{
				Id: &labapi.Dut_Id{Value: "AnyId"},
				DutType: &labapi.Dut_Chromeos{
					Chromeos: &labapi.Dut_ChromeOS{
						Ssh: &labapi.IpEndpoint{Address: "c6-r8-rack7-host7", Port: 0},
						Servo: &labapi.Servo{
							Present: true,
							ServodAddress: &labapi.IpEndpoint{
								Address: "c6-r7-r7-labstation",
								Port:    9999,
							},
						},
					},
				},
			},
			DutServer:       &labapi.IpEndpoint{Address: "cros-dut2", Port: 80},
			ProvisionServer: &labapi.IpEndpoint{Address: "cros-provision2", Port: 80},
		},
		{
			Dut: &labapi.Dut{
				Id: &labapi.Dut_Id{Value: "AnyId"},
				DutType: &labapi.Dut_Chromeos{
					Chromeos: &labapi.Dut_ChromeOS{
						Ssh: &labapi.IpEndpoint{Address: "0:0:0:0:0:ffff:7f00:1", Port: 0},
					},
				},
			},
		},
	}

	for i, wanted := range expected {
		dut := input[i]
		got, err := FillDUTInfo(dut, wanted.Role)
		if err != nil {
			t.Errorf("Cannot get address for dut %v: %v", dut, err)
		}
		if diff := cmp.Diff(got, wanted); diff != "" {
			t.Errorf("DownloadPrivateBundlesRequest mismatch (-got +want):\n%s", diff)
		}
	}
}

// TestFillDUTInfo makes sure FillDUTInfo behaved as expected.
func TestFillDUTInfoExtended(t *testing.T) {
	expected := []*DutInfo{
		{
			Addr:                "127.0.0.1:2222",
			Role:                "",
			Servo:               "127.123.332.121:1337",
			DutServer:           "cros-dut0:80",
			ProvisionServer:     "cros-provision0:80",
			Board:               "Fred",
			Model:               "Flintstone",
			ServoHostname:       "127.123.332.121",
			ServoPort:           "1337",
			ServoSerial:         "8675309",
			ChameleonAudio:      true,
			ChamelonPresent:     true,
			ChamelonPeriphsList: []string{"chameleon:vga", "chameleon:hdmi"},
			AtrusAudio:          true,
			TouchMimo:           true,
			CameraboxFacing:     "front",
			CableList:           []string{"type:usbaudio"},
		},
	}
	input := []*api.CrosTestRequest_Device{
		{
			Dut: &labapi.Dut{
				Id: &labapi.Dut_Id{Value: "AnyId"},
				DutType: &labapi.Dut_Chromeos{
					Chromeos: &labapi.Dut_ChromeOS{
						Ssh: &labapi.IpEndpoint{Address: "127.0.0.1", Port: 2222},
						Servo: &labapi.Servo{
							Present: true,
							ServodAddress: &labapi.IpEndpoint{
								Address: "127.123.332.121",
								Port:    1337,
							},
							Serial: "8675309",
						},
						DutModel: &labapi.DutModel{
							BuildTarget: "Fred",
							ModelName:   "Flintstone",
						},
						Chameleon: &labapi.Chameleon{
							Peripherals: []labapi.Chameleon_Peripheral{
								labapi.Chameleon_VGA,
								labapi.Chameleon_HDMI,
							},
							AudioBoard: true,
						},
						Audio: &labapi.Audio{
							Atrus: true,
						},
						Touch: &labapi.Touch{
							Mimo: true,
						},

						Camerabox: &labapi.Camerabox{
							Facing: labapi.Camerabox_FRONT,
						},
						Cables: []*labapi.Cable{
							{
								Type: labapi.Cable_USBAUDIO,
							},
						},
					},
				},
			},
			DutServer:       &labapi.IpEndpoint{Address: "cros-dut0", Port: 80},
			ProvisionServer: &labapi.IpEndpoint{Address: "cros-provision0", Port: 80},
		},
	}

	for i, wanted := range expected {
		dut := input[i]
		got, err := FillDUTInfo(dut, wanted.Role)
		if err != nil {
			t.Errorf("Cannot get address for dut %v: %v", dut, err)
		}
		if diff := cmp.Diff(got, wanted); diff != "" {
			t.Errorf("DownloadPrivateBundlesRequest mismatch (-got +want):\n%s", diff)
		}
	}
}
