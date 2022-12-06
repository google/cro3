// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package builder

import (
	"fmt"
	"testing"

	"github.com/google/go-cmp/cmp"
	"github.com/google/go-cmp/cmp/cmpopts"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
)

// sampleTestPlan is a minimal test plan object for use in our testing
var sampleTestPlan = &test_platform.Request_TestPlan{
	Suite: []*test_platform.Request_Suite{&test_platform.Request_Suite{Name: "test"}},
}

var testValidateAndAddDefaultsData = []struct {
	testName                string
	input                   CTPBuilder
	wantValidationErrString string
	wantCTPBuilder          CTPBuilder
}{
	{
		testName: "test happy path",
		input: CTPBuilder{
			BBService:   "cr-buildbucket.appspot.com",
			Board:       "zork",
			BuilderID:   getDefaultBuilder(),
			Image:       "zork-release/R107-15117.103.0",
			ImageBucket: "chromeos-image-archive",
			Pool:        "xolabs-satlab",
			Priority:    140,
			TestPlan:    sampleTestPlan,
			TimeoutMins: 360,
		},
		wantValidationErrString: "",
		wantCTPBuilder: CTPBuilder{
			BBService:   "cr-buildbucket.appspot.com",
			Board:       "zork",
			BuilderID:   getDefaultBuilder(),
			Image:       "zork-release/R107-15117.103.0",
			ImageBucket: "chromeos-image-archive",
			Pool:        "xolabs-satlab",
			Priority:    140,
			TestPlan:    sampleTestPlan,
			TimeoutMins: 360,
		},
	},
	{
		testName: "test defaults",
		input: CTPBuilder{
			Board:    "zork",
			Image:    "zork-release/R107-15117.103.0",
			Pool:     "xolabs-satlab",
			TestPlan: sampleTestPlan,
		},
		wantValidationErrString: "",
		wantCTPBuilder: CTPBuilder{
			BBService:   "cr-buildbucket.appspot.com",
			Board:       "zork",
			BuilderID:   getDefaultBuilder(),
			Image:       "zork-release/R107-15117.103.0",
			ImageBucket: "chromeos-image-archive",
			Pool:        "xolabs-satlab",
			Priority:    140,
			TestPlan:    sampleTestPlan,
			TimeoutMins: 360,
		},
	},
	{
		testName: "test missing required",
		input: CTPBuilder{
			Image:    "zork-release/R107-15117.103.0",
			Pool:     "xolabs-satlab",
			TestPlan: sampleTestPlan,
		},
		wantValidationErrString: "missing board flag",
		wantCTPBuilder:          CTPBuilder{},
	},
	{
		testName: "test missing all",
		input: CTPBuilder{
			Priority: 1,
		},
		wantValidationErrString: `missing board flag
missing pool flag
priority flag should be in [50, 255]`,
		wantCTPBuilder: CTPBuilder{},
	},
	{
		testName: "test secondary boards != images",
		input: CTPBuilder{
			Board:           "zork",
			Image:           "zork-release/R107-15117.103.0",
			Pool:            "xolabs-satlab",
			TestPlan:        sampleTestPlan,
			SecondaryBoards: []string{"zork"},
		},
		wantValidationErrString: "number of requested secondary-boards: 1 does not match with number of requested secondary-images: 0",
		wantCTPBuilder: CTPBuilder{
			BBService:   "cr-buildbucket.appspot.com",
			Board:       "zork",
			BuilderID:   getDefaultBuilder(),
			Image:       "zork-release/R107-15117.103.0",
			ImageBucket: "chromeos-image-archive",
			Pool:        "xolabs-satlab",
			Priority:    140,
			TestPlan:    sampleTestPlan,
			TimeoutMins: 360,
		},
	},
	{
		testName: "test secondary boards != models",
		input: CTPBuilder{
			Board:           "zork",
			Image:           "zork-release/R107-15117.103.0",
			Pool:            "xolabs-satlab",
			TestPlan:        sampleTestPlan,
			SecondaryBoards: []string{"zork"},
			SecondaryImages: []string{"zork-release/R107-15117.103.0"},
			SecondaryModels: []string{"eve", "eve"},
		},
		wantValidationErrString: "number of requested secondary-boards: 1 does not match with number of requested secondary-models: 2",
		wantCTPBuilder: CTPBuilder{
			BBService:   "cr-buildbucket.appspot.com",
			Board:       "zork",
			BuilderID:   getDefaultBuilder(),
			Image:       "zork-release/R107-15117.103.0",
			ImageBucket: "chromeos-image-archive",
			Pool:        "xolabs-satlab",
			Priority:    140,
			TestPlan:    sampleTestPlan,
			TimeoutMins: 360,
		},
	},
	{
		testName: "test secondary boards != lacrospath",
		input: CTPBuilder{
			Board:                "zork",
			Image:                "zork-release/R107-15117.103.0",
			Pool:                 "xolabs-satlab",
			TestPlan:             sampleTestPlan,
			SecondaryBoards:      []string{"zork"},
			SecondaryImages:      []string{"zork-release/R107-15117.103.0"},
			SecondaryLacrosPaths: []string{"foo", "bar"},
		},
		wantValidationErrString: "number of requested secondary-boards: 1 does not match with number of requested secondary-lacros-paths: 2",
		wantCTPBuilder: CTPBuilder{
			BBService:   "cr-buildbucket.appspot.com",
			Board:       "zork",
			BuilderID:   getDefaultBuilder(),
			Image:       "zork-release/R107-15117.103.0",
			ImageBucket: "chromeos-image-archive",
			Pool:        "xolabs-satlab",
			Priority:    140,
			TestPlan:    sampleTestPlan,
			TimeoutMins: 360,
		},
	},
}

// ErrToString enables safe conversions of errors to
// strings. Returns an empty string for nil errors.
func ErrToString(e error) string {
	if e == nil {
		return ""
	}
	return e.Error()
}

// TestValidateAndAddDefaults tests functionality of our validation
func TestValidateAndAddDefaults(t *testing.T) {
	t.Parallel()
	for _, tt := range testValidateAndAddDefaultsData {
		tt := tt
		t.Run(fmt.Sprintf("(%s)", tt.wantValidationErrString), func(t *testing.T) {
			t.Parallel()
			gotValidationErr := tt.input.validateAndAddDefaults()
			gotValidationErrString := ErrToString(gotValidationErr)
			if tt.wantValidationErrString != gotValidationErrString {
				t.Errorf("unexpected error: wanted '%s', got '%s'", tt.wantValidationErrString, gotValidationErrString)
			}
			if gotValidationErr == nil {
				if diff := cmp.Diff(tt.wantCTPBuilder, tt.input, cmpopts.IgnoreUnexported(buildbucketpb.BuilderID{}), cmpopts.IgnoreUnexported(test_platform.Request_TestPlan{}), cmpopts.IgnoreUnexported(test_platform.Request_Suite{})); diff != "" {
					t.Errorf("unexpected error: %s", diff)
				}
			}
		})
	}
}
