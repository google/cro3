// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"context"
	"io/ioutil"
	"log"
	"net"
	"os"
	"strings"
	"testing"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/chromiumos/config/go/test/lab/api"
	"google.golang.org/grpc"
)

func getTopology(t *testing.T, options *Options) *api.DutTopology {
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, err := newInventoryServer(
		l,
		log.New(&logBuf, "", log.LstdFlags|log.LUTC),
		options,
	)
	if err != nil {
		t.Fatalf("Failed to start InventoryServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewInventoryServiceClient(conn)
	stream, err := cl.GetDutTopology(ctx, &api.GetDutTopologyRequest{})
	if err != nil {
		t.Fatalf("Failed at InventoryServer.GetDutTopology: %v", err)
	}
	response := &api.GetDutTopologyResponse{}
	err = stream.RecvMsg(response)
	if err != nil {
		t.Fatalf("Failed at get response: %v", err)
	}
	return response.GetSuccess().DutTopology
}

// InventoryServer handles empty requests gracefully.
func TestInventoryServer_Empty(t *testing.T) {
	getTopology(t, &Options{})
}

// InventoryServer handles Dut Address/Port options passed
func TestInventoryServer_DutAddressOption(t *testing.T) {
	dutAddress := "fake-hostname"
	dutPort := 27
	dutTopology := getTopology(t, &Options{
		DutAddress: dutAddress,
		DutPort:    dutPort,
	})

	ssh := dutTopology.Duts[0].GetChromeos().GetSsh()

	if ssh.Address != dutAddress || ssh.Port != int32(dutPort) {
		t.Fatalf("Expected address: %s and port: %d; Got: %s", dutAddress, dutPort, ssh.String())
	}
}

// InventoryServer handles DutTopology config from file
func TestInventoryServer_DutTopologyConfigOption(t *testing.T) {
	dutAddress := "fake-hostname"
	tmpFile, _ := ioutil.TempFile(os.TempDir(), "fakeduttopoconfig-")
	marshal := &jsonpb.Marshaler{EmitDefaults: true, Indent: "  "}
	jsonOutput, _ := marshal.MarshalToString(&api.DutTopology{
		Duts: []*api.Dut{
			{
				DutType: &api.Dut_Chromeos{
					Chromeos: &api.Dut_ChromeOS{
						Ssh: &api.IpEndpoint{
							Address: dutAddress,
						},
					},
				},
			},
		},
	})

	dutTopoConfig := []byte(jsonOutput)
	tmpFile.Write(dutTopoConfig)
	tmpFile.Close()

	defer os.Remove(tmpFile.Name())

	dutTopology := getTopology(t, &Options{
		DutTopologyConfigPath: tmpFile.Name(),
	})

	ssh := dutTopology.Duts[0].GetChromeos().GetSsh()

	if ssh.Address != dutAddress {
		t.Fatalf("Failed to load config from file %s", tmpFile.Name())
	}
}

// InventoryServer errors on conflicting config/address options
func TestInventoryServer_DutConfig_DutAddress_Exclusive(t *testing.T) {
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	svr, err := newInventoryServer(
		l,
		log.New(&logBuf, "", log.LstdFlags|log.LUTC),
		&Options{
			DutAddress:            "fake",
			DutTopologyConfigPath: "somepath",
		},
	)
	if svr != nil || err == nil || !strings.Contains(err.Error(), "exclusive") {
		t.Fatalf("Expected error for invalid server options")
	}
}
