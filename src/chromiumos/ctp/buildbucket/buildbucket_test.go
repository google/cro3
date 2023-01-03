// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package buildbucket

import (
	"context"
	"net/http"
	"strings"
	"testing"

	"github.com/google/go-cmp/cmp"
	"github.com/google/go-cmp/cmp/cmpopts"
	"go.chromium.org/luci/auth"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/grpc/prpc"
	"google.golang.org/grpc"

	"go.chromium.org/chromiumos/platform/dev-util/src/chromiumos/ctp/site"
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
		BuilderID: builderID,
	}

	if diff := cmp.Diff(wantClient, c, cmpopts.IgnoreUnexported(Client{}, buildbucketpb.BuilderID{})); diff != "" {
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

// Fake client for testing
type fakeBBClient struct{}

// GetBuild returns a build with the appropriate ID
// Also puts the fields we input in request the SummaryMarkdown field for verification
func (fakeBBClient) GetBuild(ctx context.Context, in *buildbucketpb.GetBuildRequest, opts ...grpc.CallOption) (*buildbucketpb.Build, error) {
	b := &buildbucketpb.Build{
		Id:              in.Id,
		SummaryMarkdown: strings.Join(in.Fields.GetPaths(), ", "),
	}

	return b, nil
}

// ScheduleBuild returns an empty build object
func (fakeBBClient) ScheduleBuild(ctx context.Context, in *buildbucketpb.ScheduleBuildRequest, opts ...grpc.CallOption) (*buildbucketpb.Build, error) {
	return &buildbucketpb.Build{}, nil
}

var testGetBuildData = []struct {
	name        string
	inputID     int64
	inputFields []string
	want        *buildbucketpb.Build
}{
	{
		name:    "no fields",
		inputID: 123,
		want: &buildbucketpb.Build{
			Id:              123,
			SummaryMarkdown: "*",
		},
	},
	{
		name:        "fields",
		inputID:     123,
		inputFields: []string{"foo", "bar"},
		want: &buildbucketpb.Build{
			Id:              123,
			SummaryMarkdown: "foo, bar",
		},
	},
}

func TestGetBuild(t *testing.T) {
	t.Parallel()
	for _, tt := range testGetBuildData {
		tt := tt
		c := Client{
			client:    fakeBBClient{},
			BuilderID: &buildbucketpb.BuilderID{},
		}
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got, _ := c.GetBuild(context.Background(), tt.inputID, tt.inputFields...)
			if diff := cmp.Diff(tt.want.Id, got.Id); diff != "" {
				t.Errorf("unexpected diff in id: (%s)", diff)
			}
			if diff := cmp.Diff(tt.want.SummaryMarkdown, got.SummaryMarkdown); diff != "" {
				t.Errorf("unexpected diff in fields (%s)", diff)
			}
		})
	}
}
