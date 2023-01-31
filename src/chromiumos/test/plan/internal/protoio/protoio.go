// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package protoio contains helper methods for proto I/O done by the testplan
// tool.
package protoio

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"

	"github.com/golang/glog"
	protov1 "github.com/golang/protobuf/proto"
	"google.golang.org/protobuf/encoding/protojson"
	"google.golang.org/protobuf/proto"
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
func WriteJsonl[M proto.Message](messages []M, outPath string) error {
	outFile, err := os.Create(outPath)
	if err != nil {
		return err
	}
	defer outFile.Close()

	for _, m := range messages {
		jsonBytes, err := protojson.Marshal(m)
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

// FilepathAsJsonpb returns a copy of path, with the extension changed to
// ".jsonpb". If path is the empty string, an empty string is returned. Note
// that this function makes no attempt to check if the input path already has a
// jsonproto extension; i.e. if path is "a/b/test.jsonpb", the exact same path
// will be returned. Thus, it is up to the caller to check the returned path
// is different if this is required.
func FilepathAsJsonpb(path string) string {
	ext := filepath.Ext(path)
	if ext == "" {
		return ""
	}
	return path[0:len(path)-len(ext)] + ".jsonpb"
}
