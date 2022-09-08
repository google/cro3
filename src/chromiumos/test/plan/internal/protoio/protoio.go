// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package protoio contains helper methods for proto I/O done by the testplan
// tool.
package protoio

import (
	"io/ioutil"
	"os"
	"strings"

	"github.com/golang/glog"
	protov1 "github.com/golang/protobuf/proto"
	"google.golang.org/protobuf/encoding/protojson"
)

// ReadBinaryOrJSONPb reads path into m, attempting to parse as both a binary
// and json encoded proto.
//
// This function is meant as a convenience so the CLI can take either json or
// binary protos as input. This function guesses at whether to attempt to parse
// as binary or json first based on path's suffix.
func ReadBinaryOrJSONPb(path string, m protov1.Message) error {
	b, err := ioutil.ReadFile(path)
	if err != nil {
		return err
	}

	unmarshalOpts := protojson.UnmarshalOptions{DiscardUnknown: true}

	if strings.HasSuffix(path, ".jsonpb") || strings.HasSuffix(path, ".jsonproto") {
		glog.Infof("Attempting to parse %q as jsonpb first", path)

		err = unmarshalOpts.Unmarshal(b, protov1.MessageV2(m))
		if err == nil {
			return nil
		}

		glog.Warningf("Parsing %q as jsonpb failed (%q), attempting to parse as binary pb", path, err)

		return protov1.Unmarshal(b, m)
	}

	glog.Infof("Attempting to parse %q as binary pb first", path)

	err = protov1.Unmarshal(b, m)
	if err == nil {
		return nil
	}

	glog.Warningf("Parsing %q as binarypb failed, attempting to parse as jsonpb", path)

	return unmarshalOpts.Unmarshal(b, protov1.MessageV2(m))
}

// WriteJsonl writes a newline-delimited json file containing messages to outPath.
func WriteJsonl(messages []protov1.Message, outPath string) error {
	outFile, err := os.Create(outPath)
	if err != nil {
		return err
	}
	defer outFile.Close()

	for _, m := range messages {
		jsonBytes, err := protojson.Marshal(protov1.MessageV2(m))
		if err != nil {
			return err
		}

		jsonBytes = append(jsonBytes, []byte("\n")...)

		if _, err = outFile.Write([]byte(jsonBytes)); err != nil {
			return err
		}
	}

	return nil
}
