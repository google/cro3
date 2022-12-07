// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package buildbucket

import (
	"context"
	"net/http"
	"strings"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/buildbucket"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/lucictx"
	"google.golang.org/grpc/metadata"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/src/chromiumos/ctp/common"
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

// ScheduleBuild schedules a new build (of the client's builder) with the given
// properties, tags, bot dimensions, and Buildbucket priority, and returns the
// scheduled build.
//
// Buildbucket requests take properties of type *structpb.Struct. To simplify
// the conversion from other data structures to Structs, ScheduleBuild accepts
// properties of type map[string]interface{}, where interface{} can be any of
// Go's basic types (bool, string, number type, byte, or rune), a proto message
// (in the form protoreflect.ProtoMessage), or a nested map[string]interface{}
// that fulfils the same requirements recursively.
//
// NOTE: Buildbucket priority is separate from internal swarming priority.
func (c *Client) ScheduleBuild(ctx context.Context, props map[string]interface{}, dims map[string]string, tags map[string]string, priority int32) (*buildbucketpb.Build, error) {
	propStruct, err := common.MapToStruct(props)

	if err != nil {
		return nil, err
	}

	// Check if there's a parent build for the task to be launched.
	// If a ScheduleBuildToken can be found in the Buildbucket section of LUCI_CONTEXT,
	// it will be the token for the parent build.
	// Attaching the token to the ScheduleBuild request will enable Buildbucket to
	// track the parent/child build relationship between the build with the token
	// and this new build.
	bbCtx := lucictx.GetBuildbucket(ctx)
	// Do not attach the buildbucket token if it's empty or the build is a led build.
	// Because led builds are not real Buildbucket builds and they don't have
	// real buildbucket tokens, so we cannot make them any builds's parent,
	// even for the builds they scheduled.
	if bbCtx != nil && bbCtx.GetScheduleBuildToken() != "" && bbCtx.GetScheduleBuildToken() != buildbucket.DummyBuildbucketToken {
		ctx = metadata.NewOutgoingContext(ctx, metadata.Pairs(buildbucket.BuildbucketTokenHeader, bbCtx.ScheduleBuildToken))
	}

	request := &buildbucketpb.ScheduleBuildRequest{
		Builder:    c.builderID,
		Properties: propStruct,
		Dimensions: bbDims(dims),
		Tags:       bbTags(tags),
		Priority:   priority,
	}
	build, err := c.client.ScheduleBuild(ctx, request)
	if err != nil {
		return nil, errors.Annotate(err, "schedule build").Err()
	}
	return build, nil
}

// bbDims converts the given map[string]string of bot dimensions to the
// required []*buildbucketpb.RequestedDimension type for Buildbucket requests.
func bbDims(dims map[string]string) []*buildbucketpb.RequestedDimension {
	var bbDimList []*buildbucketpb.RequestedDimension
	for key, val := range dims {
		bbDimList = append(bbDimList, &buildbucketpb.RequestedDimension{
			Key:   strings.Trim(key, " "),
			Value: strings.Trim(val, " "),
		})
	}
	return bbDimList
}

// bbTags converts the given map[string]string of Buildbucket tags to the
// required []*buildbucketpb.StringPair type for Buildbucket requests.
func bbTags(tags map[string]string) []*buildbucketpb.StringPair {
	var bbTagList []*buildbucketpb.StringPair
	for key, val := range tags {
		bbTagList = append(bbTagList, &buildbucketpb.StringPair{
			Key:   strings.Trim(key, " "),
			Value: strings.Trim(val, " "),
		})
	}
	return bbTagList
}
