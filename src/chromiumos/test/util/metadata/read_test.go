// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package metadata

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/golang/protobuf/proto"
	"github.com/google/go-cmp/cmp"
	"go.chromium.org/chromiumos/config/go/test/api"
)

// TestReadDir makes to ReadDir read all metadata files in a directory without errors.
func TestReadDir(t *testing.T) {

	tmpDir, err := ioutil.TempDir("", "cros-test_TestReadDir_*")
	if err != nil {
		t.Fatal("Failed to create tmpdir: ", err)
	}

	defer os.RemoveAll(tmpDir)

	if err := os.MkdirAll(filepath.Join(tmpDir, "tast"), 0755); err != nil {
		t.Fatal("Failed to create directory tast: ", err)
	}
	if err := os.MkdirAll(filepath.Join(tmpDir, "tauto"), 0755); err != nil {
		t.Fatal("Failed to create directory tauto: ", err)
	}
	expectedMetadata := map[string][]*api.TestCaseMetadata{

		"tast": {
			{
				TestCase: &api.TestCase{
					Id: &api.TestCase_Id{
						Value: "tast/test001",
					},
					Name: "tast001",
					Tags: []*api.TestCase_Tag{
						{Value: "attr1"},
						{Value: "attr2"},
					},
				},
				TestCaseExec: &api.TestCaseExec{
					TestHarness: &api.TestHarness{
						TestHarnessType: &api.TestHarness_Tast_{
							Tast: &api.TestHarness_Tast{},
						},
					},
				},
				TestCaseInfo: &api.TestCaseInfo{
					Owners: []*api.Contact{
						{Email: "someone1@chromium.org"},
						{Email: "someone2@chromium.org"},
					},
				},
			},
		},
		"tauto": {
			{
				TestCase: &api.TestCase{
					Id: &api.TestCase_Id{
						Value: "tauto/test002",
					},
					Name: "test002",
					Tags: []*api.TestCase_Tag{
						{Value: "attr1"},
						{Value: "attr2"},
					},
				},
				TestCaseExec: &api.TestCaseExec{
					TestHarness: &api.TestHarness{
						TestHarnessType: &api.TestHarness_Tauto_{
							Tauto: &api.TestHarness_Tauto{},
						},
					},
				},
				TestCaseInfo: &api.TestCaseInfo{
					Owners: []*api.Contact{
						{Email: "someone1@chromium.org"},
						{Email: "someone2@chromium.org"},
					},
				},
			},
		},
	}
	if err := writeMetadata(&api.TestCaseMetadataList{Values: expectedMetadata["tast"]}, tmpDir, "tast"); err != nil {
		t.Fatal("Failed to write tast metadata: ", err)
	}

	if err := writeMetadata(&api.TestCaseMetadataList{Values: expectedMetadata["tauto"]}, tmpDir, "tast"); err != nil {
		t.Fatal("Failed to write tauto metadata: ", err)
	}

	mdList, err := ReadDir(tmpDir)
	if err != nil {
		t.Fatal("Failed to read metadata directory: ", err)
	}
	actualMetadata := make(map[string][]*api.TestCaseMetadata)
	for _, m := range mdList.Values {
		if strings.HasPrefix(m.TestCase.Id.Value, "tast") {
			actualMetadata["tast"] = append(actualMetadata["tast"], m)
			continue
		}
		if strings.HasPrefix(m.TestCase.Id.Value, "tauto") {
			actualMetadata["tauto"] = append(actualMetadata["tauto"], m)
			continue
		}
		t.Errorf("Unexpected metadata: %+v", m)
	}

	if cmp.Equal(expectedMetadata, actualMetadata, cmp.Comparer(proto.Equal)) {
		t.Errorf("ReadDir return unexpected result: got %v; want %v", actualMetadata, expectedMetadata)
	}
}

func writeMetadata(mdList *api.TestCaseMetadataList, tmpDir, name string) error {
	b, err := proto.Marshal(mdList)
	if err != nil {
		return err
	}
	if err := ioutil.WriteFile(filepath.Join(tmpDir, name, name+".pb"), b, 0644); err != nil {
		return err
	}
	return nil
}
