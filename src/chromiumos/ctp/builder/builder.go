// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package builder

import (
	"context"
	"fmt"
	"strings"
	"time"

	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/luci/auth"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/errors"
	"google.golang.org/protobuf/types/known/durationpb"

	"go.chromium.org/chromiumos/platform/dev-util/src/chromiumos/ctp/buildbucket"
	"go.chromium.org/chromiumos/platform/dev-util/src/chromiumos/ctp/common"
	"go.chromium.org/chromiumos/platform/dev-util/src/chromiumos/ctp/site"
)

// CTP builder contains fields needed to send a build to CTP
type CTPBuilder struct {
	// AuthOptions represent configuration for LUCI Auth used when sending
	// builds to buildbucket such as the location of the client tokens or scope
	// These should match the options used to log into LUCI
	// For more context, see https://pkg.go.dev/go.chromium.org/luci/auth
	AuthOptions *auth.Options
	// BBClient is the client used to create buildbucket requests
	// If nil, a client will be created as part of scheduling the request
	BBClient buildbucket.BBClient
	// BBService is the URL of the buildbucket service to run against
	// Defaults to https://cr-buildbucket.appspot.com/
	BBService string // TODO
	// Board is the board to run against
	// Board is REQUIRED
	Board string
	// BuilderID is the builder we want to submit the CTP requests to.
	// If not provided, will submit to chromeos/testplatform/cros_test_platform builder
	BuilderID *buildbucketpb.BuilderID // TODO
	// CFT determines whether we will use CFT to run tests.
	CFT bool
	// CTPBuildTags are any tags that should be associated solely with the CTP
	// build and not passed down to the test_runner builds.
	CTPBuildTags map[string]string
	// Dimensions contains required dimensions for swarming bots
	Dimensions map[string]string
	// Image is the image to be provisioned on the DUT when running the test
	// Image is REQUIRED
	Image string
	// ImageBucket is the GS bucket name where we will pull the image
	// If not provided, ImageBucket will be `chromeos-image-archive`
	ImageBucket string
	// Keyvals will be passed into autotest
	Keyvals map[string]string
	// LacrosPath is the GS path to a Lacros object
	LacrosPath string
	// MaxRetries controls the amount of times CTP will attempt to retry a test
	MaxRetries int
	// Model specifies what model a test should run on
	Model string
	// Pool specifies what `label-pool` dimension we should run a test on
	// Pool is REQUIRED
	Pool string
	// Priority is the swarming priority to run tests under
	// Priority and QSAccount cannot both be set
	Priority int64
	// Properties are any input properties to the CTP build that aren't a part
	// of the CTP request built. Should not include a key with `requests`
	Properties map[string]interface{}
	// ProvisionLabels are any labels impacting how we provision a test
	ProvisionLabels map[string]string
	// QSAccount is what QuotaScheduler account the tests should run under
	// Priority and QSAccount cannot both be set
	QSAccount string
	// SecondaryBoards is a list containing the boards of any secondary devices
	SecondaryBoards []string
	// SecondaryModels is a list containing the models of any secondary devices
	// Should either be equal to the length of SecondaryBoards or zero
	SecondaryModels []string
	// SecondaryImages is a list containing the images of any secondary devices
	// Should be of equal length to SecondaryBoards or zero
	SecondaryImages []string
	// SecondaryBoards is a list containing the LacrosPath of any secondary devices
	// Should either be equal to the length of SecondaryBoards or zero
	SecondaryLacrosPaths []string
	// TestPlan is the test plan we want to execute
	// These should not be built by hand, instead using a method in the CTP client lib
	TestPlan *test_platform.Request_TestPlan
	// TestRunnerBuildTags are any tags that should be applied to the
	// downstream Test Runner builds.
	TestRunnerBuildTags map[string]string
	// TimeoutMins is the timeout of the CTP run in minutes
	// If not set, will default to 360
	TimeoutMins int
	// UseScheduke determines if we use Scheduke to schedule the CTP build
	UseScheduke bool
}

// ScheduleCTPBuild sends a buildbucket request based on CTPBuilder
func (c *CTPBuilder) ScheduleCTPBuild(ctx context.Context) (*buildbucketpb.Build, error) {
	c.validateAndAddDefaults()

	// `testRunnerTags` are only applied to the downstream test runner builds
	testRunnerTags := c.testRunnerTags()
	ctpRequest, err := c.TestPlatformRequest(testRunnerTags)
	if err != nil {
		return nil, err
	}

	c.addRequestToProperties(ctpRequest)

	if c.AuthOptions == nil {
		c.AuthOptions = &site.DefaultAuthOptions
	}

	ctpBBClient, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	// ctpBuildTags are only applied to the parent CTP build
	ctpBuildTags := c.ctpTags()

	// Parent cros_test_platform builds run on generic GCE bots at the default
	// priority, so we pass zero values for the dimensions and priority of the
	// parent build.
	//
	// buildProps contains separate dimensions and priority values to apply to
	// the child test_runner builds that will be launched by the parent build.
	return buildbucket.ScheduleBuild(ctx, c.Properties, nil, ctpBuildTags, 0, ctpBBClient, c.BuilderID)
}

const (
	defaultImageBucket      = "chromeos-image-archive"
	defaultSwarmingPriority = 140
	defaultSwarmingTimeout  = 360

	minSwarmingPriority = 50
	maxSwarmingPriority = 255
)

func getDefaultBuilder() *buildbucketpb.BuilderID {
	return &buildbucketpb.BuilderID{
		Project: "chromeos",
		Bucket:  "testplatform",
		Builder: "cros_test_platform",
	}
}

// getClient returns a new high level client using either an existing BBClient
// or creating one on demand
func (c *CTPBuilder) getClient(ctx context.Context) (buildbucket.BBClient, error) {
	// use the struct's builder if exists
	if c.BBClient != nil {
		return c.BBClient, nil
	}

	// otherwise build one for throwaway use
	ctpBBClient, err := buildbucket.NewClient(ctx, c.BBService, c.AuthOptions, buildbucket.NewHTTPClient)
	if err != nil {
		return nil, err
	}
	return ctpBBClient, nil
}

// validateAndAddDefaults checks for any required fields and adds appropriate
// defaults to necessary fields
func (c *CTPBuilder) validateAndAddDefaults() error {
	if c.ImageBucket == "" {
		c.ImageBucket = defaultImageBucket
	}
	if c.Priority == 0 {
		c.Priority = defaultSwarmingPriority
	}
	if c.TimeoutMins == 0 {
		c.TimeoutMins = defaultSwarmingTimeout
	}
	if c.BuilderID == nil {
		c.BuilderID = getDefaultBuilder()
	}
	if c.BBService == "" {
		c.BBService = "cr-buildbucket.appspot.com"
	}

	var errors []string
	if c.Board == "" {
		errors = append(errors, "missing board flag")
	}
	if c.Pool == "" {
		errors = append(errors, "missing pool flag")
	}
	if c.Priority < minSwarmingPriority || c.Priority > maxSwarmingPriority {
		errors = append(errors, fmt.Sprintf("priority flag should be in [%d, %d]", minSwarmingPriority, maxSwarmingPriority))
	}
	// For multi-DUTs result reporting purpose we need board info, so even if
	// explicit secondary models request, we need to ensure board info is also
	// provided and the count matches.
	if len(c.SecondaryModels) > 0 && len(c.SecondaryBoards) != len(c.SecondaryModels) {
		errors = append(errors, fmt.Sprintf("number of requested secondary-boards: %d does not match with number of requested secondary-models: %d", len(c.SecondaryBoards), len(c.SecondaryModels)))
	}
	// If OS provision is required for secondary DUTs, then we require an image name for
	// each secondary DUT.
	if len(c.SecondaryImages) > 0 && len(c.SecondaryBoards) != len(c.SecondaryImages) {
		errors = append(errors, fmt.Sprintf("number of requested secondary-boards: %d does not match with number of requested secondary-images: %d", len(c.SecondaryBoards), len(c.SecondaryImages)))
	}
	// If lacros provision is required for secondary DUTs, then we require a path for
	// each secondary DUT.
	if len(c.SecondaryLacrosPaths) > 0 && len(c.SecondaryLacrosPaths) != len(c.SecondaryBoards) {
		errors = append(errors, fmt.Sprintf("number of requested secondary-boards: %d does not match with number of requested secondary-lacros-paths: %d", len(c.SecondaryBoards), len(c.SecondaryLacrosPaths)))
	}

	if len(errors) > 0 {
		return fmt.Errorf(strings.Join(errors, "\n"))
	}
	return nil
}

const (
	// containerMetadataURLSuffix is the URL suffix for the container metadata
	// URL in the ChromeOS image archive.
	containerMetadataURLSuffix = "metadata/containers.jsonpb"
)

// ctpTags returns the tags we should attach to the parent CTP build.
func (c *CTPBuilder) ctpTags() map[string]string {
	tags := map[string]string{}

	for k, v := range c.CTPBuildTags {
		tags[k] = v
	}
	for k, v := range c.genericTags() {
		tags[k] = v
	}

	return tags
}

// testRunnerTags returns the tags we should attach to each test runner build
// by combining user supplied tags with generic metadata tags.
func (c *CTPBuilder) testRunnerTags() map[string]string {
	tags := map[string]string{}

	for k, v := range c.TestRunnerBuildTags {
		tags[k] = v
	}
	for k, v := range c.genericTags() {
		tags[k] = v
	}

	return tags
}

// genericTags generates a set of metadata tags that should be applied to both
// CTP builds as well as the downstream test runner builds.
func (c *CTPBuilder) genericTags() map[string]string {
	tags := map[string]string{}

	// Add metadata tags.
	if c.Board != "" {
		tags["label-board"] = c.Board
	}
	if c.Model != "" {
		tags["label-model"] = c.Model
	}
	if c.Pool != "" {
		tags["label-pool"] = c.Pool
	}
	if c.Image != "" {
		tags["label-image"] = c.Image
	}
	// Only surface the priority if Quota Account was unset.
	if c.QSAccount != "" {
		tags["label-quota-account"] = c.QSAccount
	} else if c.Priority != 0 {
		tags["label-priority"] = fmt.Sprint(c.Priority)
	}

	return tags
}

// TestPlatformRequest constructs a cros_test_platform.Request from the given CTPBuilder
func (c *CTPBuilder) TestPlatformRequest(buildTags map[string]string) (*test_platform.Request, error) {
	softwareDependencies, err := c.softwareDependencies()
	if err != nil {
		return nil, err
	}
	gsPath := fmt.Sprintf("gs://%s/%s", c.ImageBucket, c.Image)

	request := &test_platform.Request{
		TestPlan: c.TestPlan,
		Params: &test_platform.Request_Params{
			FreeformAttributes: &test_platform.Request_Params_FreeformAttributes{
				SwarmingDimensions: common.ToKeyvalSlice(c.Dimensions),
			},
			HardwareAttributes: &test_platform.Request_Params_HardwareAttributes{
				Model: c.Model,
			},
			SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
				BuildTarget: &chromiumos.BuildTarget{Name: c.Board},
			},
			SoftwareDependencies: softwareDependencies,
			Scheduling:           c.schedulingParams(),
			Decorations: &test_platform.Request_Params_Decorations{
				AutotestKeyvals: c.Keyvals,
				Tags:            common.ToKeyvalSlice(buildTags),
			},
			Retry: c.retryParams(),
			Metadata: &test_platform.Request_Params_Metadata{
				TestMetadataUrl:        gsPath,
				DebugSymbolsArchiveUrl: gsPath,
				ContainerMetadataUrl:   gsPath + "/" + containerMetadataURLSuffix,
			},
			Time: &test_platform.Request_Params_Time{
				MaximumDuration: durationpb.New(
					time.Duration(c.TimeoutMins) * time.Minute),
			},
			RunViaCft:           c.CFT,
			ScheduleViaScheduke: c.UseScheduke,
		},
	}
	// Handling multi-DUTs use case if secondaryBoards provided.
	if len(c.SecondaryBoards) > 0 {
		request.Params.SecondaryDevices = c.secondaryDevices()
	}
	return request, nil
}

// softwareDependencies constructs test_platform.Request_Params_SoftwareDependency
// from fields in softwareDependencies
func (c *CTPBuilder) softwareDependencies() ([]*test_platform.Request_Params_SoftwareDependency, error) {
	deps, err := softwareDepsFromProvisionLabels(c.ProvisionLabels)
	if err != nil {
		return nil, err
	}
	if c.ImageBucket != "" {
		deps = append(deps, &test_platform.Request_Params_SoftwareDependency{
			Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuildGcsBucket{
				ChromeosBuildGcsBucket: c.ImageBucket,
			}})
	}
	if c.Image != "" {
		deps = append(deps, &test_platform.Request_Params_SoftwareDependency{
			Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: c.Image},
		})
	}
	if c.LacrosPath != "" {
		deps = append(deps, &test_platform.Request_Params_SoftwareDependency{
			Dep: &test_platform.Request_Params_SoftwareDependency_LacrosGcsPath{LacrosGcsPath: c.LacrosPath},
		})
	}
	return deps, nil
}

// softwareDepsFromProvisionLabels parses the given provision labels into a
// []*test_platform.Request_Params_SoftwareDependency.
func softwareDepsFromProvisionLabels(labels map[string]string) ([]*test_platform.Request_Params_SoftwareDependency, error) {
	var deps []*test_platform.Request_Params_SoftwareDependency
	for label, value := range labels {
		dep := &test_platform.Request_Params_SoftwareDependency{}
		switch label {
		// These prefixes are interpreted by autotest's provisioning behavior;
		// they are defined in the autotest repo, at utils/labellib.py
		case "cros-version":
			dep.Dep = &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{
				ChromeosBuild: value,
			}
		case "fwro-version":
			dep.Dep = &test_platform.Request_Params_SoftwareDependency_RoFirmwareBuild{
				RoFirmwareBuild: value,
			}
		case "fwrw-version":
			dep.Dep = &test_platform.Request_Params_SoftwareDependency_RwFirmwareBuild{
				RwFirmwareBuild: value,
			}
		default:
			return nil, errors.Reason("invalid provisionable label %s", label).Err()
		}
		deps = append(deps, dep)
	}
	return deps, nil
}

// schedulingParams constructs Swarming scheduling params from test run flags.
func (c *CTPBuilder) schedulingParams() *test_platform.Request_Params_Scheduling {
	s := &test_platform.Request_Params_Scheduling{}

	if managedPool, isManaged := managedPool(c.Pool); isManaged {
		s.Pool = &test_platform.Request_Params_Scheduling_ManagedPool_{ManagedPool: managedPool}
	} else {
		s.Pool = &test_platform.Request_Params_Scheduling_UnmanagedPool{UnmanagedPool: c.Pool}
	}

	// Priority and Quota Scheduler account cannot coexist in a CTP request.
	// Only attach priority if no quota account is specified.
	if c.QSAccount != "" {
		s.QsAccount = c.QSAccount
	} else {
		s.Priority = c.Priority
	}

	return s
}

// secondaryDevices constructs secondary devices data for a test platform request
func (c *CTPBuilder) secondaryDevices() []*test_platform.Request_Params_SecondaryDevice {
	var secondary_devices []*test_platform.Request_Params_SecondaryDevice
	for i, b := range c.SecondaryBoards {
		sd := &test_platform.Request_Params_SecondaryDevice{
			SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
				BuildTarget: &chromiumos.BuildTarget{Name: b},
			},
		}
		if len(c.SecondaryImages) > 0 && c.SecondaryImages[i] != "" {
			sd.SoftwareDependencies = append(sd.SoftwareDependencies, &test_platform.Request_Params_SoftwareDependency{
				Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: c.SecondaryImages[i]},
			})
		}
		if len(c.SecondaryModels) > 0 {
			sd.HardwareAttributes = &test_platform.Request_Params_HardwareAttributes{
				Model: c.SecondaryModels[i],
			}
		}
		if len(c.SecondaryLacrosPaths) > 0 && c.SecondaryLacrosPaths[i] != "" {
			sd.SoftwareDependencies = append(sd.SoftwareDependencies, &test_platform.Request_Params_SoftwareDependency{
				Dep: &test_platform.Request_Params_SoftwareDependency_LacrosGcsPath{LacrosGcsPath: c.SecondaryLacrosPaths[i]},
			})
		}
		secondary_devices = append(secondary_devices, sd)
	}
	return secondary_devices
}

// retryParams constructs test_platform.Request_Params_Retry from CTPBuilder
func (c *CTPBuilder) retryParams() *test_platform.Request_Params_Retry {
	return &test_platform.Request_Params_Retry{
		Max:   int32(c.MaxRetries),
		Allow: c.MaxRetries != 0,
	}
}

// managedPool returns the test_platform.Request_Params_Scheduling_ManagedPool
// matching the given pool string, and returns false if no match was found.
func managedPool(pool string) (test_platform.Request_Params_Scheduling_ManagedPool, bool) {
	// Attempt to handle common pool name format discrepancies.
	pool = strings.ToUpper(pool)
	pool = strings.Replace(pool, "-", "_", -1)
	pool = strings.Replace(pool, "DUT_POOL_", "MANAGED_POOL_", 1)

	enum, ok := test_platform.Request_Params_Scheduling_ManagedPool_value[pool]
	if !ok {
		return 0, false
	}
	return test_platform.Request_Params_Scheduling_ManagedPool(enum), true
}

// addRequestToProperties adds the test platform request to the user-supplied
// properties in preparation to send to CTP builders
func (c *CTPBuilder) addRequestToProperties(r *test_platform.Request) {
	if c.Properties == nil {
		c.Properties = map[string]interface{}{}
	}

	c.Properties["requests"] = map[string]interface{}{
		// Convert to protoreflect.ProtoMessage for easier type comparison.
		"default": r.ProtoReflect().Interface(),
	}
}