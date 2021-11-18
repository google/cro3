// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package starlark

import (
	"fmt"

	"github.com/golang/protobuf/proto"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/payload"
	test_api_v1 "go.chromium.org/chromiumos/config/go/test/api/v1"
	starlarkproto "go.starlark.net/lib/proto"
	"go.starlark.net/starlark"
	"go.starlark.net/starlarkstruct"
	"google.golang.org/protobuf/reflect/protoreflect"
)

// protoAccessorBuiltin returns a Builtin that provides access to Message m.
func protoAccessorBuiltin(name string, m proto.Message) *starlark.Builtin {
	return starlark.NewBuiltin(
		name,
		func(thread *starlark.Thread, fn *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
			// Check that no args are passed.
			err := starlark.UnpackArgs(fn.Name(), args, kwargs)
			if err != nil {
				return nil, err
			}

			// The proto must be marshalled to bytes and then unmarshalled to
			// get a starlarkproto.Message.
			bytes, err := proto.Marshal(m)
			if err != nil {
				return nil, err
			}

			message, err := starlarkproto.Unmarshal(
				proto.MessageReflect(m).Descriptor(), bytes,
			)
			if err != nil {
				return nil, err
			}

			return message, nil
		},
	)
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

			// Assert the Value passed to the function is a
			// test_api_v1.HWTestPlan, and add to result.
			starlarkMessage, ok := starlarkValue.(*starlarkproto.Message)
			if !ok {
				return nil, fmt.Errorf("arg to %s must be a HWTestPlan, got %q", fn.Name(), starlarkValue)
			}

			protoMessage := proto.MessageV1(starlarkMessage.Message())

			test_plan, ok := protoMessage.(*test_api_v1.HWTestPlan)
			if !ok {
				return nil, fmt.Errorf("arg to %s must be a HWTestPlan, got %q", fn.Name(), protoMessage)
			}

			*result = append(*result, test_plan)
			return starlark.None, nil
		},
	)
}

// getAllMessageDescriptors returns MessageDescriptors for all messages that:
//
// 1. Are the type of a field defined by root.
// 2. Recursively satisfy 1., i.e. getAllMessageDescriptors is called
//    recursively on each MessageDescriptor found on root.
//
// Each MessageDescriptor can be used to define a constructor
// function in Starlark, so that a full instance of root can be built in
// Starlark.
func getAllMessageDescriptors(root protoreflect.MessageDescriptor) []protoreflect.MessageDescriptor {
	// Map from full name -> descriptor to avoid duplicates.
	result := map[protoreflect.FullName]protoreflect.MessageDescriptor{
		root.FullName(): root,
	}

	for i := 0; i < root.Fields().Len(); i++ {
		desc := root.Fields().Get(i).Message()
		// desc is non-nil if the field is a message.
		if desc != nil {
			// Add the field to result, and call getAllMessageDescriptors
			// recursively.
			result[desc.FullName()] = desc
			for _, innerDesc := range getAllMessageDescriptors(desc) {
				result[innerDesc.FullName()] = innerDesc
			}
		}
	}

	// Get the unique set of MessageDescriptors out of the map.
	resultValues := make([]protoreflect.MessageDescriptor, 0, len(result))
	for _, v := range result {
		resultValues = append(resultValues, v)
	}

	return resultValues
}

// protoCtorBuiltins returns a set of Builtins to construct m and all messages
// that are recursively fields of m. For example, for message:
//
// message M1 {
//   M2 f1 = 1;
// }
//
// message M2 {
//   string f2 = 1;
// }
//
// Starlark builtins to construct 'M1' and 'M2' are returned:
//
// testmessage = M1(f1=M2(f2='abc'))
func protoCtorBuiltins(m proto.Message) starlark.StringDict {
	result := starlark.StringDict{}

	protoDescs := getAllMessageDescriptors(proto.MessageReflect(m).Descriptor())

	for _, protoDesc := range protoDescs {
		descriptor := starlarkproto.MessageDescriptor{
			Desc: protoDesc,
		}

		result[string(protoDesc.Name())] = starlark.NewBuiltin(
			// TODO(b/182898188): Convert names to snake_case.
			string(protoDesc.Name()),
			func(thread *starlark.Thread, fn *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
				return descriptor.CallInternal(
					thread, args, kwargs,
				)
			},
		)
	}

	return result
}

// mergeStringDicts merges the keys and values from d2 into d1 and returns the
// result. Note that if a key from d2 is already in d1, d1 is overwritten.
func mergeStringDicts(d1, d2 starlark.StringDict) starlark.StringDict {
	for k, v := range d2 {
		d1[k] = v
	}
	return d1
}

// ExecTestPlan executes the Starlark file planFilename.
// Builtins are provided to planFilename to access buildMetadataList and
// flatConfigList.
//
// TODO(b/182898188): Provide more extensive documentation of Starlark execution
// environment.
func ExecTestPlan(
	planFilename string,
	buildMetadataList *buildpb.SystemImage_BuildMetadataList,
	flatConfigList *payload.FlatConfigList,
) ([]*test_api_v1.HWTestPlan, error) {
	thread := &starlark.Thread{
		Name: fmt.Sprintf("exec_%s", planFilename),
	}

	getBuildMetadataBuiltin := protoAccessorBuiltin(
		"get_build_metadata", buildMetadataList,
	)

	getFlatConfigListBuiltin := protoAccessorBuiltin(
		"get_flat_config_list", flatConfigList,
	)

	var test_plans []*test_api_v1.HWTestPlan
	addHWTestPlanBuiltin := buildAddHWTestPlanBuiltin(&test_plans)

	testplanModule := &starlarkstruct.Module{
		Name: "testplan",
		Members: mergeStringDicts(
			starlark.StringDict{
				getBuildMetadataBuiltin.Name():  getBuildMetadataBuiltin,
				getFlatConfigListBuiltin.Name(): getFlatConfigListBuiltin,
				addHWTestPlanBuiltin.Name():     addHWTestPlanBuiltin,
			},
			protoCtorBuiltins(&test_api_v1.HWTestPlan{}),
		),
	}

	predeclared := starlark.StringDict{
		testplanModule.Name: testplanModule,
	}

	_, err := starlark.ExecFile(thread, planFilename, nil, predeclared)
	if err != nil {
		return nil, fmt.Errorf("failed executing Starlark file %q: %w", planFilename, err)
	}

	return test_plans, nil
}
