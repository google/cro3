// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"encoding/json"
	"fmt"
	"testing"

	"github.com/google/go-cmp/cmp"

	"chromiumos/test/execution/cmd/cros-test/internal/device"
)

func TestGenHostInfoStore(t *testing.T) {
	primary := &device.DutInfo{
		Addr:          "foo",
		Phase:         "aphase",
		Sku:           "asku",
		Model:         "amodel",
		Board:         "aboard",
		HWID:          "123abc",
		ServoHostname: "foo-bar.cros",
	}
	expected := make(map[string]string)
	expected["HWID"] = primary.HWID
	expected["servo_host"] = primary.ServoHostname
	expectedLabels := []string{
		fmt.Sprintf("board:%v", primary.Board),
		fmt.Sprintf("model:%v", primary.Model),
		fmt.Sprintf("sku:%v", primary.Sku),
		fmt.Sprintf("phase:%v", primary.Phase)}
	ExpectedhostInfo := &HostInfo{Attributes: expected, Labels: expectedLabels}
	b, err := json.MarshalIndent(ExpectedhostInfo, "", "    ")

	c, err := genHostInfoFileContent(primary)
	if err != nil {
		t.Errorf("Got unexpected err: %v", err)
	}
	fmt.Println(string(c))
	fmt.Println(string(b))

	if diff := cmp.Diff(c, b); diff != "" {
		t.Errorf("Expected != Actual: %v", diff)
	}

}
