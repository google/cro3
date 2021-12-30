// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package starlark

import (
	"fmt"

	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/starlark/starlarkproto"
	"google.golang.org/protobuf/reflect/protodesc"
	"google.golang.org/protobuf/reflect/protoregistry"
	"google.golang.org/protobuf/types/descriptorpb"
)

// findAllDescriptors finds FileDescriptorProtos for the proto file at path,
// and all files it imports, both directly and recursively.
//
// Descriptors ordered topologically, so they can be passed to
// starlarkproto.NewDescriptorSet.
//
// visited keeps track of files already visited, so only one descriptor is
// returned for each file.
func findAllDescriptors(path string, visited stringset.Set) ([]*descriptorpb.FileDescriptorProto, error) {
	if !visited.Add(path) {
		return nil, nil // Already visited, return no new descriptors.
	}

	fd, err := protoregistry.GlobalFiles.FindFileByPath(path)
	if err != nil {
		return nil, err
	}

	var allFdps []*descriptorpb.FileDescriptorProto
	fdp := protodesc.ToFileDescriptorProto(fd)

	for _, d := range fdp.GetDependency() {
		fdps, err := findAllDescriptors(d, visited)
		if err != nil {
			return nil, fmt.Errorf("error finding descriptors for %s: %w", d, err)
		}

		allFdps = append(allFdps, fdps...)
	}

	return append(allFdps, fdp), nil
}

// buildProtoLoader returns a Loader seeded with descriptors for HWTestPlan and
// all its dependencies.
func buildProtoLoader() (*starlarkproto.Loader, error) {
	visited := stringset.New(0)

	fdps, err := findAllDescriptors("chromiumos/test/api/v1/plan.proto", visited)
	if err != nil {
		return nil, err
	}

	ds, err := starlarkproto.NewDescriptorSet("testplan", fdps, []*starlarkproto.DescriptorSet{})
	if err != nil {
		return nil, err
	}

	loader := starlarkproto.NewLoader()
	if err := loader.AddDescriptorSet(ds); err != nil {
		return nil, err
	}

	return loader, nil
}
