// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package starlark

import (
	_ "go.chromium.org/chromiumos/infra/proto/go/lab"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/starlark/starlarkproto"
	"google.golang.org/protobuf/reflect/protodesc"
	"google.golang.org/protobuf/reflect/protoregistry"
	"google.golang.org/protobuf/types/descriptorpb"
)

// findAllDescriptors finds FileDescriptorProtos for the proto files in path,
// and all files they import, both directly and recursively.
//
// Descriptors are ordered topologically, so they can be passed to
// starlarkproto.NewDescriptorSet.
//
// visited keeps track of files already visited, so only one descriptor is
// returned for each file.
func findAllDescriptors(paths []string, visited stringset.Set) ([]*descriptorpb.FileDescriptorProto, error) {
	var allFdps []*descriptorpb.FileDescriptorProto

	for _, path := range paths {
		if !visited.Add(path) {
			continue
		}

		fd, err := protoregistry.GlobalFiles.FindFileByPath(path)
		if err != nil {
			return nil, err
		}

		fdp := protodesc.ToFileDescriptorProto(fd)
		depFdps, err := findAllDescriptors(fdp.GetDependency(), visited)
		if err != nil {
			return nil, err
		}

		allFdps = append(allFdps, depFdps...)
		allFdps = append(allFdps, fdp)
	}

	return allFdps, nil
}

// buildProtoLoader returns a Loader seeded with descriptors for HWTestPlan,
// ConfigBundle and all their dependencies.
func buildProtoLoader() (*starlarkproto.Loader, error) {
	visited := stringset.New(0)

	fdps, err := findAllDescriptors(
		[]string{
			"chromiumos/test/api/v1/plan.proto",
			"chromiumos/config/payload/config_bundle.proto",
			"lab/license.proto",
		},
		visited,
	)
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
