// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package buildbucket

import (
	"context"
	"net/http"

	"go.chromium.org/luci/auth"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/src/chromiumos/ctp/site"
)

// Client provides helper methods to interact with Buildbucket builds.
type Client struct {
	client    buildbucketpb.BuildsClient
	builderID *buildbucketpb.BuilderID
}

// HttpClientGenerator is a type that facilitates testing
type HttpClientGenerator func(ctx context.Context, o *auth.Options) (*http.Client, error)

// NewClient returns a new client to interact with Buildbucket builds from the
// given builder.
func NewClient(
	ctx context.Context,
	builder *buildbucketpb.BuilderID,
	bbService string,
	opts *auth.Options,
	httpClientGenerator HttpClientGenerator,
) (*Client, error) {
	httpClient, err := httpClientGenerator(ctx, opts)
	if err != nil {
		return nil, err
	}

	prpcClient := &prpc.Client{
		C:       httpClient,
		Host:    bbService,
		Options: site.DefaultPRPCOptions,
	}

	return &Client{
		client:    buildbucketpb.NewBuildsPRPCClient(prpcClient),
		builderID: builder,
	}, nil
}

// NewHTTPClient returns an HTTP client with authentication set up.
func NewHTTPClient(ctx context.Context, o *auth.Options) (*http.Client, error) {
	a := auth.NewAuthenticator(ctx, auth.SilentLogin, *o)

	c, err := a.Client()
	if err != nil {
		return nil, errors.Annotate(err, "failed to create HTTP client").Err()
	}
	return c, nil
}
