// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"context"
	"log"
	"net"
	"testing"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"
)

// TestDutServer_Empty tests if DutServer can handle emtpy requst without problem.
func TestDutServer_Empty(t *testing.T) {
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, err := newDutServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC))
	if err != nil {
		t.Fatalf("Failed to start DutServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	if _, err := cl.ProvisionDut(ctx, &api.ProvisionDutRequest{}); err != nil {
		t.Fatalf("Failed at api.ProvisionDut: %v", err)
	}
}
