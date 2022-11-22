// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package portdiscovery

import (
	"os"
	"testing"
)

var util = PortDiscovery{}

func TestWriteMetadata(t *testing.T) {
	t.Cleanup(cleanupMetaFile)
	meta := Metadata{Name: "cros-provision", Port: "8024", Version: "1.2"}
	err := util.WriteMetadata(meta)
	if err != nil {
		t.Fatalf(err.Error())
	}
}

func TestWriteMetadata_append(t *testing.T) {
	t.Cleanup(cleanupMetaFile)
	meta := Metadata{Name: "cros-provision", Port: "8024", Version: "1.2"}
	util.WriteMetadata(meta)
	meta = Metadata{Port: "8025"}
	err := util.WriteMetadata(meta)
	if err != nil {
		t.Fatalf(err.Error())
	}
}

func TestWriteMetadata_invalidMetadata(t *testing.T) {
	t.Cleanup(cleanupMetaFile)
	meta := Metadata{Name: "cros-provision", Version: "1.2"}
	err := util.WriteMetadata(meta)
	if err == nil {
		t.Fatalf("expect error")
	}
}

func cleanupMetaFile() {
	os.Remove(util.getMetaFilePath())
}

func TestGetPortFromAddress_ipv6(t *testing.T) {
	expect := "38809"
	port, err := util.GetPortFromAddress("[::]:38809")
	if err != nil {
		t.Fatalf(err.Error())
	}
	if port != expect {
		t.Fatalf("Result doesn't match\nexpect: %v\nactual: %v", expect, port)
	}
}

func TestGetPortFromAddress_ipv4(t *testing.T) {
	expect := "38809"
	port, err := util.GetPortFromAddress("127.0.0.1:38809")
	if err != nil {
		t.Fatalf(err.Error())
	}
	if port != expect {
		t.Fatalf("Result doesn't match\nexpect: %v\nactual: %v", expect, port)
	}
}

func TestGetPortFromAddress_invalidAddress(t *testing.T) {
	expect := ""
	port, err := util.GetPortFromAddress("38809")
	if err == nil {
		t.Fatalf("Expect error")
	}
	if port != expect {
		t.Fatalf("Result doesn't match\nexpect: %v\nactual: %v", expect, port)
	}
}
