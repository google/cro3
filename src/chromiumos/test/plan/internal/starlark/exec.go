// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package starlark

import (
	"fmt"

	"github.com/golang/protobuf/proto"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/payload"
	starlarkproto "go.starlark.net/lib/proto"
	"go.starlark.net/starlark"
	"go.starlark.net/starlarkstruct"
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

// ExecTestPlan executes the Starlark file planFilename.
// Builtins are provided to planFilename to access buildMetadataList and
// flatConfigList.
//
// TODO(b/182898188): Provide builtin to add test plans.
// TODO(b/182898188): Provide more extensive documentation of Starlark execution
// environment.
func ExecTestPlan(
	planFilename string,
	buildMetadataList *buildpb.SystemImage_BuildMetadataList,
	flatConfigList *payload.FlatConfigList,
) error {
	thread := &starlark.Thread{
		Name: fmt.Sprintf("exec_%s", planFilename),
	}

	getBuildMetadataBuiltin := protoAccessorBuiltin(
		"get_build_metadata", buildMetadataList,
	)

	getFlatConfigListBuiltin := protoAccessorBuiltin(
		"get_flat_config_list", flatConfigList,
	)

	testplanModule := &starlarkstruct.Module{
		Name: "testplan",
		Members: starlark.StringDict{
			getBuildMetadataBuiltin.Name():  getBuildMetadataBuiltin,
			getFlatConfigListBuiltin.Name(): getFlatConfigListBuiltin,
		},
	}

	predeclared := starlark.StringDict{
		testplanModule.Name: testplanModule,
	}

	_, err := starlark.ExecFile(thread, planFilename, nil, predeclared)
	if err != nil {
		return fmt.Errorf("failed executing Starlark file %q: %w", planFilename, err)
	}

	return nil
}
