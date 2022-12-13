// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package builder

import (
	"context"

	"go.chromium.org/luci/auth"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"

	"go.chromium.org/chromiumos/platform/dev-util/src/chromiumos/ctp/buildbucket"
	"go.chromium.org/chromiumos/platform/dev-util/src/chromiumos/ctp/site"
)

// ClientArgs are whatever args the bb client used to fetch the builds should use
// All fields have a sensible default for "standard" chromeos usage
type ClientArgs struct {
	AuthOptions *auth.Options
	BBService string
}

// GetBuild fetches a build with the fields specified. If no fields are specified, all fields are returned
func GetBuild(ctx context.Context, args *ClientArgs, ID int64, fields ...string) (*buildbucketpb.Build, error) {
	if args.BBService == "" {
		args.BBService = "cr-buildbucket.appspot.com"
	}
	if args.AuthOptions == nil {
		args.AuthOptions = &site.DefaultAuthOptions
	}

	ctpBBClient, err := buildbucket.NewClient(ctx, &buildbucketpb.BuilderID{}, args.BBService, args.AuthOptions, buildbucket.NewHTTPClient)
	if err != nil {
		return nil, err
	}

	return ctpBBClient.GetBuild(ctx, ID, fields...)
}