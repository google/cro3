// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package rdb_client

import (
	"context"
	"fmt"
	"os/exec"
	"strings"
)

type RdbClient struct {
	RdbExecutablePath           string
	ResultAdapterExecutablePath string
}

// RdbRpcConfig will be used to construct rdb rpc command
type RdbRpcConfig struct {
	ServiceName        string
	MethodName         string
	IncludeUpdateToken bool
}

// RpcCommand creates the rdb rpc command
func (rdbClient *RdbClient) RpcCommand(ctx context.Context, rdbRpcConfig *RdbRpcConfig) (*exec.Cmd, error) {
	var args []string

	if rdbRpcConfig.IncludeUpdateToken {
		args = append(args, "-include-update-token")
	}

	rpcArgs := []string{"rpc", rdbRpcConfig.ServiceName, rdbRpcConfig.MethodName}
	rpcArgs = append(rpcArgs, args...)

	cmd := exec.CommandContext(ctx, rdbClient.RdbExecutablePath, rpcArgs...)

	return cmd, nil
}

// RdbQueryConfig will be used to construct rdb query command
type RdbQueryConfig struct {
	InvocationIds                 []string
	TestResultFields              []string
	VariantsWithUnexpectedResults bool
	Merge                         bool
	Limit                         int
}

// QueryCommand creates the rdb query command
func (rdbClient *RdbClient) QueryCommand(ctx context.Context, rdbQueryConfig *RdbQueryConfig) (*exec.Cmd, error) {
	args := []string{"-json", "-n", fmt.Sprint(rdbQueryConfig.Limit)}

	if rdbQueryConfig.VariantsWithUnexpectedResults {
		args = append(args, "-u")
	}
	if rdbQueryConfig.Merge {
		args = append(args, "-merge")
	}
	if len(rdbQueryConfig.TestResultFields) > 0 {
		args = append(args, "-tr-fields", strings.Join(rdbQueryConfig.TestResultFields, ","))
	}
	args = append(args, rdbQueryConfig.InvocationIds...)

	queryArgs := []string{"query"}
	queryArgs = append(queryArgs, args...)

	cmd := exec.CommandContext(ctx, rdbClient.RdbExecutablePath, queryArgs...)

	return cmd, nil
}

// RdbStreamConfig will be used to construct rdb stream command
type RdbStreamConfig struct {
	BaseTags                map[string]string
	BaseVariant             map[string]string
	Cmds                    []string
	TestIdPrefix            string
	TestLocationBase        string
	LocationTagsFile        string
	ResultFormat            string
	ResultFile              string
	ArtifactDir             string
	Realm                   string
	RequireBuildInvocation  bool
	ExonerateUnexpectedPass bool
	Include                 bool
	CoerceNegativeDuration  bool
}

// StreamCommand creates the rdb stream command
func (rdbClient *RdbClient) StreamCommand(ctx context.Context, rdbStreamConfig *RdbStreamConfig) (*exec.Cmd, error) {

	streamArgs := []string{"stream"}

	if strings.TrimSpace(rdbStreamConfig.TestIdPrefix) != "" {
		streamArgs = append(streamArgs, "-test-id-prefix", rdbStreamConfig.TestIdPrefix)
	}

	if strings.TrimSpace(rdbStreamConfig.TestLocationBase) != "" {
		streamArgs = append(streamArgs, "-test-location-base", rdbStreamConfig.TestLocationBase)
	}

	if strings.TrimSpace(rdbStreamConfig.LocationTagsFile) != "" {
		streamArgs = append(streamArgs, "-location-tags-file", rdbStreamConfig.LocationTagsFile)
	}

	if rdbStreamConfig.Include {
		if strings.TrimSpace(rdbStreamConfig.Realm) != "" {
			streamArgs = append(streamArgs, "-new", "-realm", rdbStreamConfig.Realm)
		} else {
			return nil, fmt.Errorf("realm cannot be empty when requested to include new realm")
		}
	}

	if rdbStreamConfig.CoerceNegativeDuration {
		streamArgs = append(streamArgs, "-coerce-negative-duration")
	}

	if rdbStreamConfig.ExonerateUnexpectedPass {
		streamArgs = append(streamArgs, "-exonerate-unexpected-pass")
	}

	for k, v := range rdbStreamConfig.BaseVariant {
		streamArgs = append(streamArgs, "-var", fmt.Sprintf("%s:%s", k, v))
	}

	for k, v := range rdbStreamConfig.BaseTags {
		streamArgs = append(streamArgs, "-tag", fmt.Sprintf("%s:%s", k, v))
	}

	streamArgs = append(streamArgs, "--")
	streamArgs = append(streamArgs, rdbStreamConfig.Cmds...)

	cmd := exec.CommandContext(ctx, rdbClient.RdbExecutablePath, streamArgs...)

	return cmd, nil
}
