// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package starlark

import (
	"context"
	"fmt"
	"path/filepath"

	protov1 "github.com/golang/protobuf/proto"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/payload"
	test_api_v1 "go.chromium.org/chromiumos/config/go/test/api/v1"
	"go.chromium.org/luci/starlark/interpreter"
	"go.chromium.org/luci/starlark/starlarkproto"
	"go.starlark.net/starlark"
	"go.starlark.net/starlarkstruct"
	"google.golang.org/protobuf/proto"
)

// protoAccessorBuiltin returns a Builtin that provides access to Message m.
func protoAccessorBuiltin(
	protoLoader *starlarkproto.Loader,
	name string,
	m protov1.Message,
) *starlark.Builtin {
	return starlark.NewBuiltin(
		name,
		func(thread *starlark.Thread, fn *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
			// Check that no args are passed.
			err := starlark.UnpackArgs(fn.Name(), args, kwargs)
			if err != nil {
				return nil, err
			}

			// starlarkproto.MessageType.MessageFromProto should work here, but
			// panics because some descriptors are not exactly the same. Marshal
			// to bytes and then use starlarkproto.FromWirePB for now.
			bytes, err := protov1.Marshal(m)
			if err != nil {
				return nil, err
			}

			return starlarkproto.FromWirePB(
				protoLoader.MessageType(protov1.MessageReflect(m).Descriptor()),
				bytes,
			)
		},
	)
}

// starlarkValueToProto converts value to proto Message m. An error is returned
// if value is not a starlarkproto.Message, with a protoreflect.FullName that is
// exactly the same as the protoreflect.FullName of m.
func starlarkValueToProto(value starlark.Value, m protov1.Message) error {
	mName := protov1.MessageReflect(m).Descriptor().FullName()

	// Assert value is a starlarkproto.Message.
	starlarkMessage, ok := value.(*starlarkproto.Message)
	if !ok {
		return fmt.Errorf("arg must be a %s, got %q", mName, value)
	}

	// It is not possible to use type assertions to convert the
	// starlarkproto.Message to a protov1.Message, so marshal it to bytes and
	// then unmarshal as a protov1.Message.
	//
	// First check that the full name of the message passed in exactly
	// matches the full name of m, to avoid confusing errors
	// from unmarshalling.
	starlarkProto := starlarkMessage.ToProto()

	if mName != starlarkProto.ProtoReflect().Descriptor().FullName() {
		return fmt.Errorf("arg must be a %s, got %q", mName, starlarkProto)
	}

	bytes, err := proto.Marshal(starlarkMessage.ToProto())
	if err != nil {
		return err
	}

	if err := protov1.Unmarshal(bytes, m); err != nil {
		return err
	}

	return nil
}

// buildAddHWTestPlanBuiltin returns a Builtin that takes a single HWTestPlan
// and adds it to result.
func buildAddHWTestPlanBuiltin(result *[]*test_api_v1.HWTestPlan) *starlark.Builtin {
	return starlark.NewBuiltin(
		"add_hw_test_plan",
		func(thread *starlark.Thread, fn *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
			var starlarkValue starlark.Value
			if err := starlark.UnpackArgs(fn.Name(), args, kwargs, "hw_test_plan", &starlarkValue); err != nil {
				return nil, err
			}

			hwTestPlan := &test_api_v1.HWTestPlan{}
			if err := starlarkValueToProto(starlarkValue, hwTestPlan); err != nil {
				return nil, fmt.Errorf("%s: %w", fn.Name(), err)
			}

			*result = append(*result, hwTestPlan)
			return starlark.None, nil
		},
	)
}

// buildAddVMTestPlanBuiltin returns a Builtin that takes a single HWTestPlan
// and adds it to result.
func buildAddVMTestPlanBuiltin(result *[]*test_api_v1.VMTestPlan) *starlark.Builtin {
	return starlark.NewBuiltin(
		"add_vm_test_plan",
		func(thread *starlark.Thread, fn *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
			var starlarkValue starlark.Value
			if err := starlark.UnpackArgs(fn.Name(), args, kwargs, "vm_test_plan", &starlarkValue); err != nil {
				return nil, err
			}

			vmTestPlan := &test_api_v1.VMTestPlan{}
			if err := starlarkValueToProto(starlarkValue, vmTestPlan); err != nil {
				return nil, fmt.Errorf("%s: %w", fn.Name(), err)
			}

			*result = append(*result, vmTestPlan)
			return starlark.None, nil
		},
	)
}

// ExecTestPlan executes the Starlark file planFilename.
// Builtins are provided to planFilename to access buildMetadataList and
// configBundleList, and add [VM,HW]TestPlans to the output.
//
// A loader is provided to load proto constructors.
func ExecTestPlan(
	ctx context.Context,
	planFilename string,
	buildMetadataList *buildpb.SystemImage_BuildMetadataList,
	configBundleList *payload.ConfigBundleList,
) ([]*test_api_v1.HWTestPlan, []*test_api_v1.VMTestPlan, error) {
	protoLoader, err := buildProtoLoader()
	if err != nil {
		return nil, nil, err
	}

	getBuildMetadataBuiltin := protoAccessorBuiltin(
		protoLoader, "get_build_metadata", buildMetadataList,
	)

	getFlatConfigListBuiltin := protoAccessorBuiltin(
		protoLoader, "get_config_bundle_list", configBundleList,
	)

	var hw_test_plans []*test_api_v1.HWTestPlan
	addHWTestPlanBuiltin := buildAddHWTestPlanBuiltin(&hw_test_plans)

	var vm_test_plans []*test_api_v1.VMTestPlan
	addVMTestPlanBuiltin := buildAddVMTestPlanBuiltin(&vm_test_plans)

	testplanModule := &starlarkstruct.Module{
		Name: "testplan",
		Members: starlark.StringDict{
			getBuildMetadataBuiltin.Name():  getBuildMetadataBuiltin,
			getFlatConfigListBuiltin.Name(): getFlatConfigListBuiltin,
			addHWTestPlanBuiltin.Name():     addHWTestPlanBuiltin,
			addVMTestPlanBuiltin.Name():     addVMTestPlanBuiltin,
		},
	}

	// The directory of planFilename is set as the main package for the
	// interpreter to run.
	planDir, planBasename := filepath.Split(planFilename)

	pkgs := map[string]interpreter.Loader{
		interpreter.MainPkg: interpreter.FileSystemLoader(planDir),
	}

	// Create a loader for proto constructors, using protoLoader. The paths are
	// based on the descriptors in protoLoader, i.e. the Starlark code will look
	// like
	// `load('@proto//chromiumos/test/api/v1/plan.proto', plan_pb = 'chromiumos.test.api.v1')`
	pkgs["proto"] = func(path string) (dict starlark.StringDict, src string, err error) {
		mod, err := protoLoader.Module(path)
		if err != nil {
			return nil, "", err
		}

		return starlark.StringDict{mod.Name: mod}, "", nil
	}

	// Init the interpreter and execute it on planBasename.
	intr := interpreter.Interpreter{
		Predeclared: starlark.StringDict{
			testplanModule.Name: testplanModule,
		},
		Packages: pkgs,
	}

	if err := intr.Init(ctx); err != nil {
		return nil, nil, err
	}

	if _, err := intr.ExecModule(ctx, interpreter.MainPkg, planBasename); err != nil {
		return nil, nil, fmt.Errorf("failed executing Starlark file %q: %w", planFilename, err)
	}

	return hw_test_plans, vm_test_plans, nil
}
