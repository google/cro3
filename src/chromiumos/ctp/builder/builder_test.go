// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package builder

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/google/go-cmp/cmp"
	"github.com/google/go-cmp/cmp/cmpopts"
	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/platform/dev-util/src/chromiumos/ctp/buildbucket"
	"go.chromium.org/chromiumos/platform/dev-util/src/chromiumos/ctp/site"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"google.golang.org/grpc"
	"google.golang.org/protobuf/types/known/durationpb"
)

// sampleTestPlan is a minimal test plan object for use in our testing
var sampleTestPlan = &test_platform.Request_TestPlan{
	Suite: []*test_platform.Request_Suite{&test_platform.Request_Suite{Name: "test"}},
}

// CmpOpts enables comparisons of the listed protos with unexported fields.
var CmpOpts = cmpopts.IgnoreUnexported(
	buildbucketpb.BuilderID{},
	chromiumos.BuildTarget{},
	durationpb.Duration{},
	test_platform.Request{},
	test_platform.Request_TestPlan{},
	test_platform.Request_Params{},
	test_platform.Request_Params_Decorations{},
	test_platform.Request_Params_FreeformAttributes{},
	test_platform.Request_Params_HardwareAttributes{},
	test_platform.Request_Params_Metadata{},
	test_platform.Request_Params_SoftwareDependency{},
	test_platform.Request_Params_Retry{},
	test_platform.Request_Params_Scheduling{},
	test_platform.Request_Params_SecondaryDevice{},
	test_platform.Request_Params_SoftwareAttributes{},
	test_platform.Request_Params_SoftwareDependency{},
	test_platform.Request_Params_Time{},
	test_platform.Request_Suite{},
)

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
			SecondaryBoards: []string{"zork", "coral"},
			SecondaryImages: []string{"sample-image"},
		},
		wantValidationErrString: "number of requested secondary-boards: 2 does not match with number of requested secondary-images: 1",
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
		t.Run(fmt.Sprintf("(%s)", tt.testName), func(t *testing.T) {
			t.Parallel()
			gotValidationErr := tt.input.validateAndAddDefaults()
			gotValidationErrString := ErrToString(gotValidationErr)
			if tt.wantValidationErrString != gotValidationErrString {
				t.Errorf("unexpected error: wanted '%s', got '%s'", tt.wantValidationErrString, gotValidationErrString)
			}
			if gotValidationErr == nil {
				if diff := cmp.Diff(tt.wantCTPBuilder, tt.input, CmpOpts); diff != "" {
					t.Errorf("unexpected error: %s", diff)
				}
			}
		})
	}
}

var testSoftwareDependenciesData = []struct {
	name          string
	input         CTPBuilder
	wantDeps      []*test_platform.Request_Params_SoftwareDependency
	wantErrString string
}{
	{
		"invalid label",
		CTPBuilder{
			ImageBucket:     "",
			Image:           "",
			ProvisionLabels: map[string]string{"foo-invalid": "bar"},
		},
		nil,
		"invalid provisionable label foo-invalid",
	},
	{
		"no deps",
		CTPBuilder{
			ImageBucket:     "",
			Image:           "",
			ProvisionLabels: nil,
		},
		nil,
		"",
	},
	{
		"bucket, image, lacros, and label",
		CTPBuilder{
			ImageBucket: "sample-bucket",
			Image:       "sample-image",
			LacrosPath:  "sample-lacros-path",
			ProvisionLabels: map[string]string{
				"fwrw-version": "foo-rw",
			},
		},
		[]*test_platform.Request_Params_SoftwareDependency{
			{Dep: &test_platform.Request_Params_SoftwareDependency_RwFirmwareBuild{RwFirmwareBuild: "foo-rw"}},
			{Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuildGcsBucket{ChromeosBuildGcsBucket: "sample-bucket"}},
			{Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: "sample-image"}},
			{Dep: &test_platform.Request_Params_SoftwareDependency_LacrosGcsPath{LacrosGcsPath: "sample-lacros-path"}},
		},
		"",
	},
}

func TestSoftwareDependencies(t *testing.T) {
	t.Parallel()
	for _, tt := range testSoftwareDependenciesData {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			gotDeps, gotErr := tt.input.softwareDependencies()
			if diff := cmp.Diff(tt.wantDeps, gotDeps, CmpOpts); diff != "" {
				t.Errorf("unexpected diff (%s)", diff)
			}
			gotErrString := ErrToString(gotErr)
			if tt.wantErrString != gotErrString {
				t.Errorf("unexpected error: wanted '%s', got '%s'", tt.wantErrString, gotErrString)
			}
		})
	}
}

var testSchedulingParamsData = []struct {
	name     string
	input    CTPBuilder
	wantDeps *test_platform.Request_Params_Scheduling
}{
	{
		"priority",
		CTPBuilder{
			Priority: 123,
			Pool:     "foobar",
		},
		&test_platform.Request_Params_Scheduling{
			Pool:     &test_platform.Request_Params_Scheduling_UnmanagedPool{UnmanagedPool: "foobar"},
			Priority: 123,
		},
	},
	{
		"qsAccount",
		CTPBuilder{
			Priority:  123,
			QSAccount: "account",
			Pool:      "foobar",
		},
		&test_platform.Request_Params_Scheduling{
			Pool:      &test_platform.Request_Params_Scheduling_UnmanagedPool{UnmanagedPool: "foobar"},
			QsAccount: "account",
		},
	},
	{
		"managed pool",
		CTPBuilder{
			Priority: 123,
			Pool:     "dut-pool-cq",
		},
		&test_platform.Request_Params_Scheduling{
			Pool:     &test_platform.Request_Params_Scheduling_ManagedPool_{ManagedPool: test_platform.Request_Params_Scheduling_MANAGED_POOL_CQ},
			Priority: 123,
		},
	},
}

func TestSchedulingParams(t *testing.T) {
	t.Parallel()
	for _, tt := range testSchedulingParamsData {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			gotDeps := tt.input.schedulingParams()
			if diff := cmp.Diff(tt.wantDeps, gotDeps, CmpOpts); diff != "" {
				t.Errorf("unexpected diff (%s)", diff)
			}
		})
	}
}

var testRetryParamsData = []struct {
	name     string
	input    CTPBuilder
	wantDeps *test_platform.Request_Params_Retry
}{
	{
		"zero",
		CTPBuilder{
			MaxRetries: 0,
		},
		&test_platform.Request_Params_Retry{
			Max:   int32(0),
			Allow: false,
		},
	},
	{
		"greater than zero",
		CTPBuilder{
			MaxRetries: 3,
		},
		&test_platform.Request_Params_Retry{
			Max:   int32(3),
			Allow: true,
		},
	},
}

func TestRetryParams(t *testing.T) {
	t.Parallel()
	for _, tt := range testRetryParamsData {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			gotDeps := tt.input.retryParams()
			if diff := cmp.Diff(tt.wantDeps, gotDeps, CmpOpts); diff != "" {
				t.Errorf("unexpected diff (%s)", diff)
			}
		})
	}
}

var testSecondaryDevicesData = []struct {
	name     string
	input    CTPBuilder
	wantDeps []*test_platform.Request_Params_SecondaryDevice
}{
	{
		"board image only",
		CTPBuilder{
			SecondaryBoards: []string{"board1", "board2"},
			SecondaryImages: []string{"board1-release/10000.0.0", "board2-release/9999.0.0"},
		},
		[]*test_platform.Request_Params_SecondaryDevice{
			{
				SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
					BuildTarget: &chromiumos.BuildTarget{Name: "board1"},
				},
				SoftwareDependencies: []*test_platform.Request_Params_SoftwareDependency{
					{Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: "board1-release/10000.0.0"}},
				},
			},
			{
				SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
					BuildTarget: &chromiumos.BuildTarget{Name: "board2"},
				},
				SoftwareDependencies: []*test_platform.Request_Params_SoftwareDependency{
					{Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: "board2-release/9999.0.0"}},
				},
			},
		},
	},
	{
		"board image model",
		CTPBuilder{
			SecondaryBoards: []string{"board1", "board2"},
			SecondaryImages: []string{"board1-release/10000.0.0", "board2-release/9999.0.0"},
			SecondaryModels: []string{"model1", "model2"},
		},
		[]*test_platform.Request_Params_SecondaryDevice{
			{
				SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
					BuildTarget: &chromiumos.BuildTarget{Name: "board1"},
				},
				SoftwareDependencies: []*test_platform.Request_Params_SoftwareDependency{
					{Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: "board1-release/10000.0.0"}},
				},
				HardwareAttributes: &test_platform.Request_Params_HardwareAttributes{
					Model: "model1",
				},
			},
			{
				SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
					BuildTarget: &chromiumos.BuildTarget{Name: "board2"},
				},
				SoftwareDependencies: []*test_platform.Request_Params_SoftwareDependency{
					{Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: "board2-release/9999.0.0"}},
				},
				HardwareAttributes: &test_platform.Request_Params_HardwareAttributes{
					Model: "model2",
				},
			},
		},
	},
	{
		"board image lacros path",
		CTPBuilder{
			SecondaryBoards:      []string{"board1", "board2"},
			SecondaryImages:      []string{"board1-release/10000.0.0", "board2-release/9999.0.0"},
			SecondaryLacrosPaths: []string{"lc1", "lc2"},
		},
		[]*test_platform.Request_Params_SecondaryDevice{
			{
				SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
					BuildTarget: &chromiumos.BuildTarget{Name: "board1"},
				},
				SoftwareDependencies: []*test_platform.Request_Params_SoftwareDependency{
					{Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: "board1-release/10000.0.0"}},
					{Dep: &test_platform.Request_Params_SoftwareDependency_LacrosGcsPath{LacrosGcsPath: "lc1"}},
				},
			},
			{
				SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
					BuildTarget: &chromiumos.BuildTarget{Name: "board2"},
				},
				SoftwareDependencies: []*test_platform.Request_Params_SoftwareDependency{
					{Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: "board2-release/9999.0.0"}},
					{Dep: &test_platform.Request_Params_SoftwareDependency_LacrosGcsPath{LacrosGcsPath: "lc2"}},
				},
			},
		},
	},
	{
		"skip image",
		CTPBuilder{
			SecondaryBoards: []string{"board1", "board2"},
			SecondaryImages: []string{"board1-release/10000.0.0", ""},
		},
		[]*test_platform.Request_Params_SecondaryDevice{
			{
				SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
					BuildTarget: &chromiumos.BuildTarget{Name: "board1"},
				},
				SoftwareDependencies: []*test_platform.Request_Params_SoftwareDependency{
					{Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: "board1-release/10000.0.0"}},
				},
			},
			{
				SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
					BuildTarget: &chromiumos.BuildTarget{Name: "board2"},
				},
			},
		},
	},
}

func TestSecondaryDevices(t *testing.T) {
	t.Parallel()
	for _, tt := range testSecondaryDevicesData {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			gotDeps := tt.input.secondaryDevices()
			if diff := cmp.Diff(tt.wantDeps, gotDeps, CmpOpts); diff != "" {
				t.Errorf("unexpected diff (%s)", diff)
			}
		})
	}
}

func TestTestPlatformRequest(t *testing.T) {
	t.Parallel()
	b := &CTPBuilder{
		Board:           "sample-board",
		ImageBucket:     "sample-bucket",
		Image:           "sample-image",
		Pool:            "MANAGED_POOL_SUITES",
		Model:           "sample-model",
		QSAccount:       "sample-qs-account",
		Priority:        100,
		MaxRetries:      0,
		TimeoutMins:     30,
		ProvisionLabels: map[string]string{"cros-version": "foo-cros"},
		Dimensions:      map[string]string{"foo-dim": "bar-dim"},
		Keyvals:         map[string]string{"foo-key": "foo-val"},
		CFT:             true,
		TestPlan:        sampleTestPlan,
		UseScheduke:     true,
	}
	buildTags := map[string]string{"foo-tag": "bar-tag"}
	wantRequest := &test_platform.Request{
		TestPlan: sampleTestPlan,
		Params: &test_platform.Request_Params{
			Scheduling: &test_platform.Request_Params_Scheduling{
				Pool:      &test_platform.Request_Params_Scheduling_ManagedPool_{ManagedPool: 3},
				QsAccount: "sample-qs-account",
			},
			FreeformAttributes: &test_platform.Request_Params_FreeformAttributes{
				SwarmingDimensions: []string{"foo-dim:bar-dim"},
			},
			HardwareAttributes: &test_platform.Request_Params_HardwareAttributes{
				Model: "sample-model",
			},
			SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
				BuildTarget: &chromiumos.BuildTarget{Name: "sample-board"},
			},
			SoftwareDependencies: []*test_platform.Request_Params_SoftwareDependency{
				{Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: "foo-cros"}},
				{Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuildGcsBucket{ChromeosBuildGcsBucket: "sample-bucket"}},
				{Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: "sample-image"}},
			},
			Decorations: &test_platform.Request_Params_Decorations{
				AutotestKeyvals: map[string]string{"foo-key": "foo-val"},
				Tags:            []string{"foo-tag:bar-tag"},
			},
			Retry: &test_platform.Request_Params_Retry{
				Max:   0,
				Allow: false,
			},
			Metadata: &test_platform.Request_Params_Metadata{
				TestMetadataUrl:        "gs://sample-bucket/sample-image",
				DebugSymbolsArchiveUrl: "gs://sample-bucket/sample-image",
				ContainerMetadataUrl:   "gs://sample-bucket/sample-image/metadata/containers.jsonpb",
			},
			Time: &test_platform.Request_Params_Time{
				MaximumDuration: durationpb.New(time.Duration(1800000000000)),
			},
			RunViaCft:           true,
			ScheduleViaScheduke: true,
		},
	}
	gotRequest, err := b.TestPlatformRequest(buildTags)
	if err != nil {
		t.Fatalf("unexpected error constructing Test Platform request: %v", err)
	}
	if diff := cmp.Diff(wantRequest, gotRequest, CmpOpts); diff != "" {
		t.Errorf("unexpected diff (%s)", diff)
	}
}

var testCTPTags = []struct {
	name  string
	input CTPBuilder
	want  map[string]string
}{
	{
		"all tags",
		CTPBuilder{
			CTPBuildTags: map[string]string{"foo": "bar", "eli": "cool"},
			Board:        "myboard",
			Model:        "mymodel",
			Pool:         "mypool",
			Image:        "myimage",
			QSAccount:    "myqs",
			Priority:     123,
		},
		map[string]string{
			"foo":                 "bar",
			"eli":                 "cool",
			"label-board":         "myboard",
			"label-model":         "mymodel",
			"label-pool":          "mypool",
			"label-image":         "myimage",
			"label-quota-account": "myqs",
		},
	},
	{
		"only manual tags",
		CTPBuilder{
			CTPBuildTags: map[string]string{"foo": "bar", "eli": "cool"},
		},
		map[string]string{
			"foo": "bar",
			"eli": "cool",
		},
	},
	{
		"priority label if no qs account",
		CTPBuilder{
			CTPBuildTags: map[string]string{"foo": "bar", "eli": "cool"},
			Priority:     123,
		},
		map[string]string{
			"foo":            "bar",
			"eli":            "cool",
			"label-priority": "123",
		},
	},
	{
		"does not pick up test runner tags",
		CTPBuilder{
			TestRunnerBuildTags: map[string]string{"foo": "bar", "eli": "cool"},
		},
		map[string]string{},
	},
}

func TestCtpTags(t *testing.T) {
	t.Parallel()
	for _, tt := range testCTPTags {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got := tt.input.CtpTags()
			if diff := cmp.Diff(tt.want, got, CmpOpts); diff != "" {
				t.Errorf("unexpected diff (%s)", diff)
			}
		})
	}
}

var testTestRunnerTags = []struct {
	name  string
	input CTPBuilder
	want  map[string]string
}{
	{
		"all tags",
		CTPBuilder{
			TestRunnerBuildTags: map[string]string{"foo": "bar", "eli": "cool"},
			Board:               "myboard",
			Model:               "mymodel",
			Pool:                "mypool",
			Image:               "myimage",
			QSAccount:           "myqs",
			Priority:            123,
		},
		map[string]string{
			"foo":                 "bar",
			"eli":                 "cool",
			"label-board":         "myboard",
			"label-model":         "mymodel",
			"label-pool":          "mypool",
			"label-image":         "myimage",
			"label-quota-account": "myqs",
		},
	},
	{
		"only manual tags",
		CTPBuilder{
			TestRunnerBuildTags: map[string]string{"foo": "bar", "eli": "cool"},
		},
		map[string]string{
			"foo": "bar",
			"eli": "cool",
		},
	},
	{
		"priority label if no qs account",
		CTPBuilder{
			TestRunnerBuildTags: map[string]string{"foo": "bar", "eli": "cool"},
			Priority:            123,
		},
		map[string]string{
			"foo":            "bar",
			"eli":            "cool",
			"label-priority": "123",
		},
	},
	{
		"does not pick up ctp tags",
		CTPBuilder{
			CTPBuildTags: map[string]string{"foo": "bar", "eli": "cool"},
		},
		map[string]string{},
	},
}

func TestTestRunnerTags(t *testing.T) {
	t.Parallel()
	for _, tt := range testCTPTags {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got := tt.input.CtpTags()
			if diff := cmp.Diff(tt.want, got, CmpOpts); diff != "" {
				t.Errorf("unexpected diff (%s)", diff)
			}
		})
	}
}

type fakeClient struct{}

func (f fakeClient) GetBuild(context.Context, *buildbucketpb.GetBuildRequest, ...grpc.CallOption) (*buildbucketpb.Build, error) {
	return nil, nil
}
func (f fakeClient) ScheduleBuild(context.Context, *buildbucketpb.ScheduleBuildRequest, ...grpc.CallOption) (*buildbucketpb.Build, error) {
	return nil, nil
}

func TestGetClient(t *testing.T) {
	tests := []struct {
		name               string
		providedClient     buildbucket.BBClient
		shouldBeFakeClient bool
	}{
		{
			name:               "client provided",
			providedClient:     fakeClient{},
			shouldBeFakeClient: true,
		},
		{
			name:               "no client",
			providedClient:     nil,
			shouldBeFakeClient: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			c := &CTPBuilder{
				AuthOptions: &site.DefaultAuthOptions,
				BBClient:    tt.providedClient,
			}
			got, _ := c.getClient(context.Background())
			if (got == fakeClient{}) != tt.shouldBeFakeClient {
				t.Errorf("expected fake client: %t, got fake client: %t", tt.shouldBeFakeClient, (got == fakeClient{}))
				return
			}
		})
	}
}

func TestCTPBuilder_addRequestToProperties(t *testing.T) {
	type fields struct {
		Properties map[string]interface{}
	}
	type args struct {
		r *test_platform.Request
	}
	tests := []struct {
		name    string
		builder *CTPBuilder
		request *test_platform.Request
		want    *CTPBuilder
	}{
		{
			"test props",
			&CTPBuilder{Properties: map[string]interface{}{"foo": "bar"}},
			&test_platform.Request{TestPlan: sampleTestPlan},
			&CTPBuilder{Properties: map[string]interface{}{
				"foo": "bar",
				"requests": map[string]interface{}{
					// Convert to protoreflect.ProtoMessage for easier type comparison.
					"default": (&test_platform.Request{TestPlan: sampleTestPlan}).ProtoReflect().Interface(),
				},
			}},
		},
		{
			"no props",
			&CTPBuilder{},
			&test_platform.Request{TestPlan: sampleTestPlan},
			&CTPBuilder{Properties: map[string]interface{}{
				"requests": map[string]interface{}{
					// Convert to protoreflect.ProtoMessage for easier type comparison.
					"default": (&test_platform.Request{TestPlan: sampleTestPlan}).ProtoReflect().Interface(),
				},
			}},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tt.builder.addRequestToProperties(tt.request)
		})
		if diff := cmp.Diff(tt.want, tt.builder, CmpOpts); diff != "" {
			t.Errorf("unexpected diff (%s)", diff)
		}
	}
}
