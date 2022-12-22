// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package rdb_lib

import (
	"context"
	"fmt"
	"log"

	"chromiumos/test/publish/clients/rdb_client"
	common_utils "chromiumos/test/publish/cmd/common-utils"

	"github.com/google/uuid"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	rdb_pb "go.chromium.org/luci/resultdb/proto/v1"
)

var (
	SupportedResultAdapterFormats = map[string]bool{"gtest": true, "json": true, "single": true, "tast": true, "skylab-test-runner": true, "cros-test-result": true}
)

const (
	// Max size allowed is 500. Keeping it 490 to be safer.
	RpcBatchSize = 490

	// Resultdb service name
	RdbServiceName = "luci.resultdb.v1.Recorder"

	// Artifacts method name
	ArtifactsMethodName = "BatchCreateArtifacts"

	// Test results method name
	TestResultsMethodName = "BatchCreateTestResults"

	// Test exoneration method name
	TestExonerationMethodName = "BatchCreateTestExonerations"

	// Missing test cases upload retries
	MissingTestCasesUploadRetries = 2

	// Rdb query result limit
	RdbQueryResultLimit = 1000
)

type RdbLib struct {
	CurrentInvocation string
	RdbClient         *rdb_client.RdbClient
}

// UploadTestResults uploads test results to rdb
func (rdblib *RdbLib) UploadTestResults(ctx context.Context, rdbStreamConfig *rdb_client.RdbStreamConfig) error {
	if rdbStreamConfig.ResultFormat == "" {
		return fmt.Errorf("result_format can not be empty for rdb upload")
	}
	if _, ok := SupportedResultAdapterFormats[rdbStreamConfig.ResultFormat]; !ok {
		return fmt.Errorf("result_format %q could not be found in supported adapter formats: %T", rdbStreamConfig.ResultFormat, SupportedResultAdapterFormats)
	}
	if rdbStreamConfig.ResultFile == "" {
		return fmt.Errorf("result_file can not be empty for rdb upload")
	}
	resultAdapterArgs := []string{rdblib.RdbClient.ResultAdapterExecutablePath, rdbStreamConfig.ResultFormat, "-result-file", rdbStreamConfig.ResultFile}

	if rdbStreamConfig.ArtifactDir != "" {
		resultAdapterArgs = append(resultAdapterArgs, "-artifact-directory", rdbStreamConfig.ArtifactDir)
	}

	resultAdapterArgs = append(resultAdapterArgs, "--", "echo")

	rdbStreamConfig.Cmds = resultAdapterArgs

	cmd, err := rdblib.RdbClient.StreamCommand(ctx, rdbStreamConfig)
	if err != nil {
		return fmt.Errorf("error in rdb upload stream command creation: %s", err.Error())
	}

	_, _, err = common_utils.RunCommand(ctx, cmd, "rdb-upload", nil, true)

	if err != nil {
		return fmt.Errorf("error in rdb-upload: %s", err.Error())
	}

	return nil
}

// UploadInvocationArtifacts uploads invocation artifacts to rdb
func (rdblib *RdbLib) UploadInvocationArtifacts(ctx context.Context, artifact *rdb_pb.Artifact) error {
	req := rdb_pb.BatchCreateArtifactsRequest{Requests: []*rdb_pb.CreateArtifactRequest{{Parent: rdblib.CurrentInvocation, Artifact: artifact}}}

	rdbRpcConfig := &rdb_client.RdbRpcConfig{ServiceName: RdbServiceName, MethodName: ArtifactsMethodName, IncludeUpdateToken: true}
	cmd, err := rdblib.RdbClient.RpcCommand(ctx, rdbRpcConfig)
	if err != nil {
		return fmt.Errorf("error in rpc command creation: %s", err.Error())
	}

	_, _, err = common_utils.RunCommand(ctx, cmd, "rdb-upload-invocation-artifacts", &req, true)

	if err != nil {
		return fmt.Errorf("error in rdb-upload-invocation-artifacts: %s", err.Error())
	}

	return nil
}

// TODO (b/241154998): we may not need ReportMissingTestCases as we can just create test results for missing cases
// and upload them as part of regular test results. Evaluate while integrating with new adapter
// and remove if this is not required.

// ReportMissingTestCases uploads missing test cases info to rdb
func (rdblib *RdbLib) ReportMissingTestCases(ctx context.Context, testNames []string, baseVariant map[string]string, buildbucketId string) error {
	if len(testNames) == 0 {
		log.Println("no missing test(s) to upload")
		return nil
	}

	variant := rdb_pb.Variant{Def: baseVariant}
	var reqsList []*rdb_pb.CreateTestResultRequest
	for _, testName := range testNames {
		testResult := rdb_pb.TestResult{TestId: testName, ResultId: buildbucketId, Status: rdb_pb.TestStatus_SKIP, Expected: false, Variant: &variant}
		testResultReq := rdb_pb.CreateTestResultRequest{Invocation: rdblib.CurrentInvocation, TestResult: &testResult}
		reqsList = append(reqsList, &testResultReq)
	}

	var batchedReqs [][]*rdb_pb.CreateTestResultRequest

	for i := 0; i < len(reqsList); i += RpcBatchSize {
		end := i + RpcBatchSize

		if end > len(reqsList) {
			end = len(reqsList)
		}

		batchedReqs = append(batchedReqs, reqsList[i:end])
	}

	for batchNum, reqs := range batchedReqs {
		batchReq := rdb_pb.BatchCreateTestResultsRequest{Invocation: rdblib.CurrentInvocation, Requests: reqs}

		rdbRpcConfig := &rdb_client.RdbRpcConfig{ServiceName: RdbServiceName, MethodName: TestResultsMethodName, IncludeUpdateToken: true}

		cmd, err := rdblib.RdbClient.RpcCommand(ctx, rdbRpcConfig)
		if err != nil {
			return fmt.Errorf("error during getting rpc command: %s", err.Error())
		}

		errMsg := ""
		for i := 0; i < MissingTestCasesUploadRetries; i++ {
			errMsg = ""
			_, _, err := common_utils.RunCommand(ctx, cmd, "rdb-upload-missing-tests", &batchReq, true)
			if err != nil {
				errMsg = fmt.Sprintf("error in rdb-upload-missing-tests batch %d: %s", batchNum, err.Error())
				log.Println(errMsg)
				continue
			}
			break
		}
		if errMsg != "" {
			return fmt.Errorf(errMsg)
		}
	}
	return nil
}

// ApplyExonerations applies exoneration to test results
func (rdblib *RdbLib) ApplyExonerations(ctx context.Context, invocationIds []string, defaultBehavior test_platform.Request_Params_TestExecutionBehavior, behaviorOverrideMap map[string]test_platform.Request_Params_TestExecutionBehavior, variantFilter map[string]string) error {
	testExecBehaviorFunc := func(testName string) test_platform.Request_Params_TestExecutionBehavior {
		overrideBehavior, ok := behaviorOverrideMap[testName]
		if !ok {
			overrideBehavior = test_platform.Request_Params_BEHAVIOR_UNSPECIFIED
		}
		if overrideBehavior > defaultBehavior {
			return overrideBehavior
		} else {
			return defaultBehavior
		}
	}

	isNonCriticalFunc := func(testResult *rdb_pb.TestResult) bool {
		testExecBehavior := testExecBehaviorFunc(testResult.GetTestId())
		isNonCritical := testExecBehavior == test_platform.Request_Params_NON_CRITICAL

		//A test results's variant must contain all attributes of the variant filter.
		resultVariantValueMap := common_utils.GetValueBoolMap(testResult.GetVariant().GetDef())
		variantFilterValueMap := common_utils.GetValueBoolMap(variantFilter)
		containsVariantFilter := common_utils.IsSubsetOf(variantFilterValueMap, resultVariantValueMap)

		return isNonCritical && containsVariantFilter
	}

	parsedIds, err := ParseInvocationIds(invocationIds)
	if err != nil {
		return err
	}

	rdbQueryConfig := &rdb_client.RdbQueryConfig{InvocationIds: parsedIds, VariantsWithUnexpectedResults: true, TestResultFields: []string{"variant", "testId", "status", "expected"}, Merge: false, Limit: RdbQueryResultLimit}
	cmd, err := rdblib.RdbClient.QueryCommand(ctx, rdbQueryConfig)
	if err != nil {
		return fmt.Errorf("error during getting query command: %s", err.Error())
	}
	stdout, _, err := common_utils.RunCommand(ctx, cmd, "rdb-query", nil, true)
	if err != nil {
		return fmt.Errorf("error during executing query command: %s", err.Error())
	}

	invMap, err := Deserialize(stdout)
	if err != nil {
		return fmt.Errorf("error during deserializing query output: %s", err.Error())
	}

	var testExonerations []*rdb_pb.TestExoneration
	for invId, inv := range invMap {
		unexpectedResults := inv.testResults
		if len(unexpectedResults) == 0 {
			log.Printf("no test results found for invocation id %s", invId)
			continue
		}

		for _, result := range unexpectedResults {
			if !result.Expected && result.Status != rdb_pb.TestStatus_PASS && isNonCriticalFunc(result) {
				explanationHtml := "failed but is not critical"
				if result.Status == rdb_pb.TestStatus_SKIP {
					explanationHtml = "unexpectedly skipped but is not critical"
				}

				testExoneration := rdb_pb.TestExoneration{TestId: result.TestId, Variant: result.Variant, ExplanationHtml: explanationHtml, Reason: rdb_pb.ExonerationReason(3)}
				testExonerations = append(testExonerations, &testExoneration)
			}
		}
	}

	if len(testExonerations) > 0 {
		err := rdblib.Exonerate(ctx, testExonerations)
		if err != nil {
			return fmt.Errorf("error during exoneration upload: %s", err.Error())
		}
	} else {
		log.Printf("no qualified test exoneration found")
	}
	return nil
}

// Exonerate exonerates test results based on provided exoneration info
func (rdblib *RdbLib) Exonerate(ctx context.Context, testExonerations []*rdb_pb.TestExoneration) error {
	if len(testExonerations) == 0 {
		return fmt.Errorf("no test exoneration info provided for exonerate command")
	}

	rdbRpcConfig := &rdb_client.RdbRpcConfig{ServiceName: RdbServiceName, MethodName: TestExonerationMethodName, IncludeUpdateToken: true}
	cmd, err := rdblib.RdbClient.RpcCommand(ctx, rdbRpcConfig)
	if err != nil {
		return fmt.Errorf("error during getting rpc command: %s", err.Error())
	}

	batchNum := 0
	for i := 0; i < len(testExonerations); i += RpcBatchSize {
		batchNum++
		end := i + RpcBatchSize

		if end > len(testExonerations) {
			end = len(testExonerations)
		}

		var createTeRequests []*rdb_pb.CreateTestExonerationRequest
		for _, te := range testExonerations[i:end] {
			createTeRequests = append(createTeRequests, &rdb_pb.CreateTestExonerationRequest{TestExoneration: te})
		}
		batchReq := rdb_pb.BatchCreateTestExonerationsRequest{Invocation: rdblib.CurrentInvocation, RequestId: uuid.New().String(), Requests: createTeRequests}

		_, _, err := common_utils.RunCommand(ctx, cmd, "rdb-rpc-batch-exoneration", &batchReq, true)
		if err != nil {
			errMsg := fmt.Sprintf("error in rdb-rpc-batch-exoneration batch %d: %s", batchNum, err.Error())
			log.Println(errMsg)
			return fmt.Errorf(errMsg)
		}
	}
	return nil
}
