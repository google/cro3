// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package driver

import (
	"encoding/json"
	"fmt"
	"sort"
	"testing"

	"chromiumos/test/execution/cmd/cros-test/internal/device"

	"github.com/google/go-cmp/cmp"
	"go.chromium.org/chromiumos/config/go/test/api"
)

// TestNewTautoArgs makes sure newTautoArgs creates the correct arguments for tauto.
func TestNewTautoArgs(t *testing.T) {
	companions := []*device.DutInfo{
		{
			Addr: "companion1",
		},
		{
			Addr: "companion2",
		},
	}
	dutServers := []string{"localhost:2222", "localhost:2223", "localhost:2224"}
	libsServer := "192.168.1.1:8675"
	primary := &device.DutInfo{
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
		Sku:                 "goat_4kb",
		Phase:               "CVT",
		BTPeers:             3,
		CacheServer:         "cache:9001",
		HWID:                "Atlas 123-34",
	}
	customAutotestArgs := &api.AutotestExecutionMetadata{
		Args: []*api.AutotestExecutionMetadata_Arg{
			{
				Flag:  "tast_list",
				Value: "tast.example.Pass",
			},
		},
	}

	expectedArgs := tautoRunArgs{
		target:   primary,
		patterns: []string{test1, test2, test3, test4, test5},
		runFlags: map[string]string{
			tautoResultsDirFlag: workDir1,
			autotestDirFlag:     "/usr/local/autotest/",
			companionFlag:       "companion1,companion2",
			dutServerFlag:       "localhost:2222,localhost:2223,localhost:2224",
			attributes:          `{"HWID":"Atlas 123-34","servo_host":"127.123.332.121","servo_port":"1337","servo_serial":"8675309"}`,
			labels:              "board:fred model:flintstone servo chameleon audio_board chameleon:vga chameleon:hdmi atrus mimo camerabox_facing:front type:usbaudio sku:goat_4kb phase:CVT working_bluetooth_btpeer:3",
			tautoArgs:           "dut_servers=localhost:2222,localhost:2223,localhost:2224 libs_server=192.168.1.1:8675 cache_endpoint=cache:9001 tast_list=tast.example.Pass",
			libsServerFlag:      "192.168.1.1:8675",
		},
		cftFlag: "--CFT",
	}

	dut := primary
	tests := []string{test1, test2, test3, test4, test5}
	args, err := newTautoArgs(dut, companions, tests, dutServers, workDir1, libsServer, customAutotestArgs)
	if err != nil {
		t.Errorf("Got err ")
	}
	if diff := cmp.Diff(args, &expectedArgs, cmp.AllowUnexported(tautoRunArgs{})); diff != "" {
		t.Errorf("Got unexpected argument from newTautoArgs (-got +want):\n%s", diff)
	}
}

// TestGenTautoArgList makes sure genTautoArgList generates the correct list of argument for tauto.
func TestGenTautoArgList(t *testing.T) {
	primary := &device.DutInfo{Addr: dut1, Role: ""}

	attrMap := make(map[string]string)
	attrMap["servo_host"] = "test_servo"
	jsonStr, _ := json.Marshal(attrMap)

	args := tautoRunArgs{
		target:   primary,
		patterns: []string{test1, test2},
		runFlags: map[string]string{
			tautoResultsDirFlag: workDir1,
			autotestDirFlag:     "/usr/local/autotest/",
			companionFlag:       "companion1,companion2",
			attributes:          fmt.Sprintf("'%v'", string(jsonStr)),
		},
		cftFlag: cft,
	}

	var expectedArgList []string

	for key, value := range args.runFlags {
		expectedArgList = append(expectedArgList, fmt.Sprintf("%v=%v", key, value))
	}
	expectedArgList = append(expectedArgList, dut1)
	expectedArgList = append(expectedArgList, test1)
	expectedArgList = append(expectedArgList, test2)
	expectedArgList = append(expectedArgList, "--CFT")

	argList := genTautoArgList(&args)

	sort.Strings(argList)
	sort.Strings(expectedArgList)

	if diff := cmp.Diff(argList, expectedArgList, cmp.AllowUnexported(tautoRunArgs{})); diff != "" {
		t.Errorf("Got unexpected argument from genTautoArgList (-got %v +want %v):\n%s", argList, expectedArgList, diff)
	}
}
