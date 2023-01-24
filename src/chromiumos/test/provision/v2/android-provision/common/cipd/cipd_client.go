// Copyright 2022 The Chromium Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/cipd/client/cipd"
	"go.chromium.org/luci/cipd/common"
	"go.chromium.org/luci/common/errors"
)

type CIPDClient interface {
	Describe(cipdPackageProto *api.CIPDPackage, describeTags, describeRefs bool) (*cipd.InstanceDescription, error)
	FetchInstanceTo(cipdPackageProto *api.CIPDPackage, packageName, instanceId, filePath string) error
}

type CIPD struct {
	ctx       context.Context
	userAgent string
}

func NewCIPDClient(ctx context.Context) *CIPD {
	return &CIPD{
		ctx:       ctx,
		userAgent: "FleetServices: AndroidProvision",
	}
}

// Describe returns information about CIPD package instances.
func (c *CIPD) Describe(cipdPackageProto *api.CIPDPackage, describeTags, describeRefs bool) (*cipd.InstanceDescription, error) {
	clientOptions := cipd.ClientOptions{
		UserAgent: fmt.Sprintf("%s; %s", c.userAgent, cipd.UserAgent),
	}
	if cipdPackageProto.GetServiceUrl() != "" {
		clientOptions.ServiceURL = cipdPackageProto.GetServiceUrl()
	}
	client, err := cipd.NewClientFromEnv(c.ctx, clientOptions)
	if err != nil {
		return nil, errors.Annotate(err, "describe package").Err()
	}
	defer client.Close(c.ctx)
	pkgVersion, err := c.getVersion(cipdPackageProto)
	if err != nil {
		return nil, errors.Annotate(err, "describe package").Err()
	}
	pin, err := client.ResolveVersion(c.ctx, cipdPackageProto.GetName(), pkgVersion)
	if err != nil {
		return nil, errors.Annotate(err, "describe package").Err()
	}
	d, err := client.DescribeInstance(c.ctx, pin, &cipd.DescribeInstanceOpts{DescribeTags: describeTags, DescribeRefs: describeRefs})
	if err != nil {
		return nil, errors.Annotate(err, "describe package").Err()
	}
	return d, nil
}

// FetchInstanceTo downloads CIPD package to a given location.
func (c *CIPD) FetchInstanceTo(cipdPackageProto *api.CIPDPackage, packageName, instanceId, filePath string) error {
	clientOptions := cipd.ClientOptions{
		UserAgent: fmt.Sprintf("%s; %s", c.userAgent, cipd.UserAgent),
	}
	if cipdPackageProto.GetServiceUrl() != "" {
		clientOptions.ServiceURL = cipdPackageProto.GetServiceUrl()
	}
	client, err := cipd.NewClientFromEnv(c.ctx, clientOptions)
	if err != nil {
		return errors.Annotate(err, "fetch instance to").Err()
	}
	defer client.Close(c.ctx)
	if err := os.MkdirAll(filepath.Dir(filePath), 0755); err != nil {
		return errors.Annotate(err, "fetch instance to").Err()
	}
	out, err := os.OpenFile(filePath, os.O_CREATE|os.O_WRONLY, 0666)
	if err != nil {
		return errors.Annotate(err, "fetch instance to").Err()
	}
	defer func() {
		out.Close()
	}()
	pin := common.Pin{
		PackageName: packageName,
		InstanceID:  instanceId,
	}
	return client.FetchInstanceTo(c.ctx, pin, out)
}

func (c *CIPD) getVersion(cipdPackageProto *api.CIPDPackage) (string, error) {
	switch v := cipdPackageProto.GetVersionOneof().(type) {
	case *api.CIPDPackage_Ref:
		return cipdPackageProto.GetRef(), nil
	case *api.CIPDPackage_Tag:
		return cipdPackageProto.GetTag(), nil
	case *api.CIPDPackage_InstanceId:
		return cipdPackageProto.GetInstanceId(), nil
	default:
		return "", fmt.Errorf("unknown CIPD version type: %T", v)
	}
}
