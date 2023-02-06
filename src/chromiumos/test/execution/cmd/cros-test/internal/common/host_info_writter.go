// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package common provide command utilities and variables for all components in
// cros-test to use.
package common

import (
	"chromiumos/test/execution/cmd/cros-test/internal/device"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
)

// HostInfo struct is the attr/label struct used to write a mimicd host info file.
type HostInfo struct {
	Attributes map[string]string `json:"attributes"`
	Labels     []string          `json:"labels"`
}

// ConvertDutTopologyToHostInfo returns attr map, label list for the attr/labels from the dut info.
func ConvertDutTopologyToHostInfo(dut *device.DutInfo) (map[string]string, []string, error) {
	attrMap, labels, err := device.AppendChromeOsLabels(dut)
	if err != nil {
		return nil, nil, fmt.Errorf("Topology failed: %v", err)
	}
	return attrMap, labels, nil
}

func genHostInfoFileContent(dut *device.DutInfo) ([]byte, error) {
	attrMap, infoLabels, err := ConvertDutTopologyToHostInfo(dut)
	if err != nil {
		return nil, fmt.Errorf("failed to convert dutotopology: %v", err)
	}

	hostInfo := &HostInfo{Attributes: attrMap, Labels: infoLabels}

	b, err := json.MarshalIndent(hostInfo, "", "    ")
	if err != nil {
		return nil, fmt.Errorf("failed to marshal hostinfo: %v", err)
	}
	return b, nil
}

// WriteHostInfoToFile writes the host_info_store file based off dutinfo to ResutsDir
func WriteHostInfoToFile(resultsDir string, hostname string, dut *device.DutInfo, log *log.Logger) error {
	content, err := genHostInfoFileContent(dut)
	if err != nil {
		return err
	}

	fp := filepath.Join(resultsDir, "host_info_store")
	err = os.Mkdir(fp, 0755)
	if err != nil {
		log.Println("failed make info dir:", err)
	}

	fn := filepath.Join(fp, fmt.Sprintf("%s.store", hostname))
	wf, err := os.Create(fn)
	if err != nil {
		return err
	}

	defer wf.Close()

	_, err = wf.Write(content)
	if err != nil {
		return err
	}

	return nil
}
