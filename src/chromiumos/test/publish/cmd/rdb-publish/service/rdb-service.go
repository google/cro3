// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package service

import (
	"context"
	"fmt"
	"log"

	"chromiumos/test/publish/clients/rdb_client"
	common_utils "chromiumos/test/publish/cmd/common-utils"
	"chromiumos/test/publish/libs/rdb_lib"

	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/chromiumos/config/go/test/api/metadata"
	"go.chromium.org/chromiumos/config/go/test/artifact"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	rdb_pb "go.chromium.org/luci/resultdb/proto/v1"
)

const (
	// Path to rdb executable
	RdbExecutablePath = "/usr/bin/rdb"

	// Path to result_adapter executable
	ResultAdapterExecutablePath = "/usr/bin/result_adapter"

	// Path to temp directory for rdb-publish
	RdbTempDirName = "rdb-publish-temp"

	// File name for test result json
	TestResultJsonFileName = "testResult.json"

	// Result format for rdb
	ResultAdapterResultFormat = "cros-test-result"
)

type RdbPublishService struct {
	RetryCount          int
	CurrentInvocationId string
	TestResultProto     *artifact.TestResult
	StainlessUrl        string
	TempDirPath         string
}

func NewRdbPublishService(req *api.PublishRequest) (*RdbPublishService, error) {
	m, err := unpackMetadata(req)
	if err != nil {
		return nil, err
	}

	if err = common_utils.ValidateRDBPublishRequest(req, m); err != nil {
		return nil, err
	}

	retryCount := 0
	if req.GetRetryCount() > 0 {
		retryCount = int(req.GetRetryCount())
	}

	return &RdbPublishService{
		RetryCount:          retryCount,
		CurrentInvocationId: m.GetCurrentInvocationId(),
		TestResultProto:     m.GetTestResult(),
		StainlessUrl:        m.GetStainlessUrl(),
	}, nil
}

func (rps *RdbPublishService) UploadToRdb(ctx context.Context) error {
	rdbClient := rdb_client.RdbClient{RdbExecutablePath: RdbExecutablePath, ResultAdapterExecutablePath: ResultAdapterExecutablePath}
	rdbLib := rdb_lib.RdbLib{CurrentInvocation: rps.CurrentInvocationId, RdbClient: &rdbClient}

	// Create temp dir if required
	if rps.TempDirPath == "" {
		dirPath, err := common_utils.MakeTempDir(ctx, "", RdbTempDirName)
		if err != nil {
			return fmt.Errorf("error during creating temp dir for rdb publish: %s", err.Error())
		}
		rps.TempDirPath = dirPath
	}

	// Write test result to file
	testResultFilePath, err := common_utils.WriteProtoToJsonFile(ctx, rps.TempDirPath, TestResultJsonFileName, rps.TestResultProto)
	if err != nil {
		return fmt.Errorf("error during writing test result proto to file: %s", err.Error())
	} else {
		log.Printf("test result file created in path: %q", testResultFilePath)
	}

	// Upload invocation artifacts
	if rps.StainlessUrl != "" {
		artifact := rdb_pb.Artifact{ArtifactId: "stainless_logs", ContentType: "", Contents: []byte(rps.StainlessUrl)}
		err := rdbLib.UploadInvocationArtifacts(ctx, &artifact)
		if err != nil {
			return fmt.Errorf("error during rdb invocation artifact upload: %s", err.Error())
		}
	}

	// Upload test results
	baseTags := map[string]string{}
	baseVariant := map[string]string{}
	config := &rdb_client.RdbStreamConfig{BaseTags: baseTags, BaseVariant: baseVariant, ResultFile: testResultFilePath, ResultFormat: ResultAdapterResultFormat}
	err = rdbLib.UploadTestResults(ctx, config)
	if err != nil {
		return fmt.Errorf("error during rdb test results upload: %s", err.Error())
	}

	// Apply exonerations
	err = rdbLib.ApplyExonerations(ctx, []string{rps.CurrentInvocationId}, test_platform.Request_Params_NON_CRITICAL, nil, nil)
	if err != nil {
		return fmt.Errorf("error during exonerations: %s", err.Error())
	}
	return nil
}

// unpackMetadata unpacks the Any metadata field into PublishGcsMetadata
func unpackMetadata(req *api.PublishRequest) (*metadata.PublishRdbMetadata, error) {
	var m metadata.PublishRdbMetadata
	if err := req.Metadata.UnmarshalTo(&m); err != nil {
		return &m, fmt.Errorf("improperly formatted input proto metadata, %s", err)
	}
	return &m, nil
}
