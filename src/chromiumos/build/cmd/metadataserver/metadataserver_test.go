// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"context"
	"log"
	"net"
	"testing"

	"go.chromium.org/chromiumos/config/go/build/api"
	"google.golang.org/grpc"
)

// MetadataServer handles empty GetDeviceConfig
func TestMetadataServer_GetDeviceConfig_Empty(t *testing.T) {
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, err := newMetadataServer(
		l,
		log.New(&logBuf, "", log.LstdFlags|log.LUTC),
	)
	if err != nil {
		t.Fatalf("Failed to start MetadataServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewMetadataServiceClient(conn)
	response, err := cl.GetDeviceConfig(ctx, &api.GetDeviceConfigRequest{})
	if err != nil {
		t.Fatalf("Failed at MetadataServer.GetDeviceConfig: %v", err)
	}
	if err != nil {
		t.Fatalf("Failed at get response: %v", err)
	}

	if response == nil {
		t.Fatalf("Failed to handle empty request")
	}
}
