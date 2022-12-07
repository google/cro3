// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package buildbucket

import (
	"context"
	"net/http"
	"testing"

	"github.com/google/go-cmp/cmp"
	"github.com/google/go-cmp/cmp/cmpopts"
	"go.chromium.org/luci/auth"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/grpc/prpc"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/src/chromiumos/ctp/site"
)

func fakeClient(ctx context.Context, o *auth.Options) (*http.Client, error) {
	return &http.Client{}, nil
}

func TestNewClient(t *testing.T) {
	t.Parallel()

	builderID := &buildbucketpb.BuilderID{
		Project: "p",
		Bucket:  "b",
		Builder: "b",
	}

	c, err := NewClient(context.Background(), builderID, "foobar", &auth.Options{}, fakeClient)
	if err != nil {
		t.Errorf(err.Error())
	}

	wantPRPCClient := &prpc.Client{
		C:       &http.Client{},
		Host:    "foobar",
		Options: site.DefaultPRPCOptions,
	}
	wantClient := &Client{
		client:    buildbucketpb.NewBuildsPRPCClient(wantPRPCClient),
		builderID: builderID,
	}

	if diff := cmp.Diff(wantClient, c, cmpopts.IgnoreUnexported(Client{})); diff != "" {
		t.Errorf("unexpected diff (%s)", diff)
	}
}

func TestBBDims(t *testing.T) {
	t.Parallel()

	dims := map[string]string{
		"foo ": " bar",
	}
	wantBBDims := []*buildbucketpb.RequestedDimension{
		{Key: "foo", Value: "bar"},
	}
	gotBBDims := bbDims(dims)
	diff := cmp.Diff(wantBBDims, gotBBDims, cmpopts.IgnoreUnexported(buildbucketpb.RequestedDimension{}))
	if diff != "" {
		t.Errorf("unexpected diff (%s)", diff)
	}
}

func TestBBTags(t *testing.T) {
	t.Parallel()

	tags := map[string]string{
		" foo": "bar ",
	}
	wantBBTags := []*buildbucketpb.StringPair{
		{Key: "foo", Value: "bar"},
	}
	gotBBTags := bbTags(tags)
	diff := cmp.Diff(wantBBTags, gotBBTags, cmpopts.IgnoreUnexported(buildbucketpb.StringPair{}))
	if diff != "" {
		t.Errorf("unexpected diff (%s)", diff)
	}
}
