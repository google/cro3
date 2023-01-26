// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"log"
	"path"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"
	"google.golang.org/grpc"

	"chromiumos/lro"
	"chromiumos/test/execution/cmd/cros-test/internal/common"
)

// ExecutionServiceServer implementation of dut_service.proto
type ExecutionServiceServer struct {
	manager       *lro.Manager
	logger        *log.Logger
	resultRootDir string
	tlwAddr       string
	metadata      *api.TestCaseMetadataList
}

// NewServer creates an execution server.
func NewServer(logger *log.Logger, resultRootDir, tlwAddr string, metadataList *api.TestCaseMetadataList) (*grpc.Server, func()) {
	s := &ExecutionServiceServer{
		manager: lro.New(),
		logger:  logger,

		resultRootDir: resultRootDir,
		tlwAddr:       tlwAddr,
		metadata:      metadataList,
	}

	server := grpc.NewServer()
	var conns []*grpc.ClientConn
	closer := func() {
		for _, conn := range conns {
			conn.Close()
		}
		conns = nil
	}
	api.RegisterExecutionServiceServer(server, s)
	longrunning.RegisterOperationsServer(server, s.manager)
	logger.Println("crostestservice listen to request at ")
	return server, closer
}

// RunTests calls the runTests flow in cros-test.
func (s *ExecutionServiceServer) RunTests(ctx context.Context, req *api.CrosTestRequest) (*longrunning.Operation, error) {
	op := s.manager.NewOperation()
	s.logger.Println("Received api.CacheRequest: ", req)

	resultsDir, err := s.loadResultsDir(req)
	if err != nil {
		return op, errors.Annotate(err, "RunTests: unable to determine results directory path").Err()
	}

	rspn, err := runTests(ctx, s.logger, resultsDir, s.tlwAddr, s.metadata, req)
	if err != nil {
		return op, errors.Annotate(err, "RunTests: failed to run test").Err()
	}
	s.logger.Printf("Test RPC Command was successful")
	// Note: We are setting the response on the LRO, rather than writing to a resultJson like CLI mode.
	s.manager.SetResult(op.Name, rspn)
	return op, nil
}

func (s *ExecutionServiceServer) loadResultsDir(req *api.CrosTestRequest) (string, error) {
	metadata, err := common.UnpackMetadata(req)
	if err != nil {
		return "", err
	}

	resultsSubDir := metadata.GetResultsSubDir()
	if resultsSubDir == "" {
		return s.resultRootDir, nil
	}

	resultsDir := path.Join(s.resultRootDir, resultsSubDir)
	s.logger.Printf("WARNING: overriding default results directory path with %v", resultsDir)
	return resultsDir, nil
}
